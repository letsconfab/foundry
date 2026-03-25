"""
Context Loader Module - Loads full context for Foreman agent
Combines GitHub files, DB config, and thread history into a unified context.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from github import Github

from models import Confab, GitHubAccount, Message, ThreadParticipant, Thread

logger = logging.getLogger(__name__)


@dataclass
class GitHubFiles:
    """GitHub file contents for a confab."""
    purpose_md: Optional[str] = None
    guardrails_md: Optional[str] = None
    tests_md: Optional[str] = None
    last_fetched: datetime = field(default_factory=datetime.now)


@dataclass
class SetupProgress:
    """Tracks confab setup progress through the 7-step creation flow."""
    completed_steps: List[int] = field(default_factory=list)
    current_stage: str = "purpose"  # purpose, participants, memory, tools, guardrails, sample_io, review
    total_steps: int = 7

    @property
    def remaining_steps(self) -> List[int]:
        """Return list of incomplete step numbers."""
        all_steps = list(range(1, self.total_steps + 1))
        return [s for s in all_steps if s not in self.completed_steps]

    @property
    def is_complete(self) -> bool:
        """Check if all steps are complete."""
        return len(self.completed_steps) >= self.total_steps


@dataclass
class ForemanContext:
    """Complete context for a Foreman session."""
    confab: Confab
    github_files: GitHubFiles
    db_config: Dict[str, Any]
    thread_history: List[Message]
    setup_progress: SetupProgress
    thread_id: Optional[int] = None


# Step number to stage name mapping
STEP_TO_STAGE = {
    1: "purpose",
    2: "participants",
    3: "memory",
    4: "tools",
    5: "guardrails",
    6: "sample_io",
    7: "review"
}

STAGE_TO_STEP = {v: k for k, v in STEP_TO_STAGE.items()}


class ContextLoader:
    """Loads and combines all context sources for Foreman."""

    def __init__(self, db: Session):
        self.db = db

    async def load_full_context(self, confab: Confab) -> ForemanContext:
        """Load complete context for a confab session."""
        # Load GitHub account for this user
        github_account = self.db.query(GitHubAccount).filter(
            GitHubAccount.user_id == confab.user_id
        ).first()

        # Load all context sources
        github_files = await self.load_github_files(confab, github_account)
        db_config = self.load_db_config(confab)
        thread_history, thread_id = await self.load_thread_history(confab.id)
        setup_progress = self.analyze_setup_progress(confab, db_config)

        return ForemanContext(
            confab=confab,
            github_files=github_files,
            db_config=db_config,
            thread_history=thread_history,
            setup_progress=setup_progress,
            thread_id=thread_id
        )

    async def load_github_files(
        self,
        confab: Confab,
        github_account: Optional[GitHubAccount]
    ) -> GitHubFiles:
        """Fetch PURPOSE.md, GUARDRAILS.md, TESTS.md from GitHub."""
        files = GitHubFiles()

        if not github_account or not github_account.access_token:
            logger.info(f"No GitHub account for confab {confab.id}")
            return files

        confab_name = confab.name
        if not confab_name or confab_name.startswith("Agent Chat"):
            logger.info(f"Confab {confab.id} has no proper name for GitHub lookup")
            return files

        try:
            g = Github(github_account.access_token)

            # Validate token
            try:
                user = g.get_user()
                logger.info(f"GitHub token valid for user: {user.login}")
            except Exception as e:
                logger.warning(f"Invalid GitHub token: {e}")
                return files

            repo_name = f"{github_account.selected_org or github_account.github_username}/{github_account.selected_repo}"
            repo = g.get_repo(repo_name)

            # Fetch each file independently (fail gracefully)
            files.purpose_md = self._fetch_github_file(repo, confab_name, "PURPOSE.md")
            files.guardrails_md = self._fetch_github_file(repo, confab_name, "GUARDRAILS.md")
            files.tests_md = self._fetch_github_file(repo, confab_name, "TESTS.md")
            files.last_fetched = datetime.now()

        except Exception as e:
            logger.error(f"Error accessing GitHub for confab {confab.id}: {e}")

        return files

    def _fetch_github_file(self, repo, confab_name: str, filename: str) -> Optional[str]:
        """Fetch a single file from GitHub, returning None on error."""
        try:
            file_path = f"confabs/{confab_name}/{filename}"
            content = repo.get_contents(file_path)
            logger.info(f"Successfully fetched {file_path}")
            return content.decoded_content.decode('utf-8')
        except Exception as e:
            logger.debug(f"Could not fetch {filename} for {confab_name}: {e}")
            return None

    def load_db_config(self, confab: Confab) -> Dict[str, Any]:
        """Build config dict from confab's new structured fields."""
        # Build config from the new OASF-aligned fields
        config = {
            "purpose": confab.purpose,
            "guardrails": confab.guardrails,
            "tests": confab.tests,
            "model_provider": confab.model_provider,
            "model_name": confab.model_name,
            "temperature": confab.temperature,
            "skills": confab.skills,
            "domains": confab.domains,
        }
        # Filter out None values
        return {k: v for k, v in config.items() if v is not None}

    async def load_thread_history(
        self,
        confab_id: int,
        limit: int = 20
    ) -> tuple[List[Message], Optional[int]]:
        """Load recent messages from the confab's thread (via ThreadParticipant)."""
        # Find thread where this confab is a participant
        participant = self.db.query(ThreadParticipant).filter(
            ThreadParticipant.participant_type == "confab",
            ThreadParticipant.participant_id == confab_id,
            ThreadParticipant.is_active == True
        ).first()

        if not participant:
            logger.info(f"No thread found for confab {confab_id}")
            return [], None

        thread_id = participant.thread_id

        # Fetch recent messages ordered by created_at
        messages = self.db.query(Message).filter(
            Message.thread_id == thread_id
        ).order_by(Message.created_at.desc()).limit(limit).all()

        # Reverse to get chronological order
        messages = list(reversed(messages))

        logger.info(f"Loaded {len(messages)} messages for thread {thread_id}")
        return messages, thread_id

    def analyze_setup_progress(self, confab: Confab, config: Dict[str, Any]) -> SetupProgress:
        """Determine which setup steps are complete based on confab.setup_progress or config."""
        progress = SetupProgress()

        # First, check confab.setup_progress field (new method)
        if confab.setup_progress and isinstance(confab.setup_progress, dict):
            completed = confab.setup_progress.get("completed_steps", [])
            if isinstance(completed, list):
                progress.completed_steps = [int(s) for s in completed if isinstance(s, (int, str))]
            current_stage = confab.setup_progress.get("current_stage")
            if current_stage:
                progress.current_stage = current_stage
                return progress

        # Fallback: determine current stage based on completed steps and config content
        progress.current_stage = self._determine_current_stage(progress.completed_steps, config)

        return progress

    def _determine_current_stage(
        self,
        completed_steps: List[int],
        config: Dict[str, Any]
    ) -> str:
        """Determine the current stage based on completed steps and config content."""
        # If explicit steps completed, use that
        if completed_steps:
            for step_num in range(1, 8):
                if step_num not in completed_steps:
                    return STEP_TO_STAGE.get(step_num, "purpose")
            return "review"  # All steps complete

        # Infer from config content
        if config.get("purpose") or config.get("purpose_text"):
            if config.get("participants"):
                if config.get("memory_enabled") is not None:
                    if config.get("tools_and_apis"):
                        if config.get("guardrails"):
                            if config.get("sample_io"):
                                return "review"
                            return "sample_io"
                        return "guardrails"
                    return "tools"
                return "memory"
            return "participants"

        return "purpose"
