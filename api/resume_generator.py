"""
Resume Prompt Generator - Creates contextual resume prompts for Foreman
Generates intelligent greetings based on conversation state and progress.
"""

import logging
from typing import Optional, List
from datetime import datetime, timedelta

from context_loader import ForemanContext, STEP_TO_STAGE

logger = logging.getLogger(__name__)


# Step descriptions for progress display
STEP_DESCRIPTIONS = {
    1: "Define the agent's purpose",
    2: "Add participants",
    3: "Configure memory settings",
    4: "Set up tools and APIs",
    5: "Establish guardrails",
    6: "Provide sample inputs/outputs",
    7: "Review and finalize"
}

# Prompts to guide users through each stage
STAGE_PROMPTS = {
    "purpose": "What would you like this agent to do? Describe its main purpose and objectives.",
    "participants": "Who should have access to this agent? You can add participant emails or skip this step.",
    "memory": "Should this agent remember conversation history? Let me know your memory preferences.",
    "tools": "What external tools or APIs should this agent have access to?",
    "guardrails": "What safety constraints or behavioral boundaries should this agent have?",
    "sample_io": "Would you like to provide example inputs and expected outputs to guide the agent's behavior?",
    "review": "Let's review what we've configured and finalize your agent."
}


class ResumePromptGenerator:
    """Generates contextual resume prompts based on conversation state."""

    def __init__(self, context: ForemanContext):
        self.context = context
        self.confab = context.confab
        self.progress = context.setup_progress
        self.history = context.thread_history
        self.github_files = context.github_files

    def generate(self) -> str:
        """Main entry point for generating resume prompt."""
        # Case 1: Brand new confab (no history)
        if not self.history:
            return self._new_confab_prompt()

        last_msg = self.history[-1]

        # Case 2: Last message was from assistant (user hasn't responded)
        if last_msg.role == "assistant":
            if self._is_question(last_msg.content):
                return self._pending_question_prompt(last_msg.content)
            return self._continue_from_statement_prompt()

        # Case 3: Last message was from user (assistant didn't respond - error recovery)
        if last_msg.role == "user":
            return self._recover_from_user_message_prompt(last_msg.content)

        # Default: General resume with progress summary
        return self._general_resume_prompt()

    def _new_confab_prompt(self) -> str:
        """Generate welcome prompt for a brand new confab."""
        confab_name = self.confab.name or "your new agent"

        return f"""Welcome! I'm the Foreman, and I'll be helping you build '{confab_name}'.

I'll guide you through a simple 7-step process to configure your agent:
1. Define purpose - What should your agent do?
2. Add participants - Who can access it?
3. Configure memory - Should it remember conversations?
4. Set up tools - What external capabilities does it need?
5. Establish guardrails - What are its safety boundaries?
6. Sample I/O - Provide example interactions
7. Review - Finalize your configuration

Let's start with the most important part: **{STAGE_PROMPTS['purpose']}**"""

    def _pending_question_prompt(self, last_assistant_message: str) -> str:
        """Remind user of a pending question from the assistant."""
        confab_name = self.confab.name or "your agent"
        progress_summary = self._format_progress_summary()

        # Extract the question portion (last sentence or paragraph with ?)
        question_hint = self._extract_question(last_assistant_message)

        return f"""Welcome back to '{confab_name}'!

{progress_summary}

**Where we left off:**
I asked you: {question_hint}

Feel free to answer that, or let me know if you'd like to do something else."""

    def _continue_from_statement_prompt(self) -> str:
        """Continue when last assistant message wasn't a question."""
        confab_name = self.confab.name or "your agent"
        progress_summary = self._format_progress_summary()
        next_step = self._get_next_step_suggestion()

        return f"""Welcome back to '{confab_name}'!

{progress_summary}

**Suggested next step:**
{next_step}

What would you like to work on?"""

    def _recover_from_user_message_prompt(self, last_user_message: str) -> str:
        """Handle case where user's last message wasn't responded to."""
        confab_name = self.confab.name or "your agent"

        # Truncate if very long
        message_preview = last_user_message[:150]
        if len(last_user_message) > 150:
            message_preview += "..."

        return f"""Welcome back to '{confab_name}'!

It looks like your last message may not have been fully processed:
> {message_preview}

Would you like me to continue from there, or would you prefer to start fresh with something else?"""

    def _general_resume_prompt(self) -> str:
        """Generate a general resume prompt with progress summary."""
        confab_name = self.confab.name or "your agent"
        progress_summary = self._format_progress_summary()
        next_step = self._get_next_step_suggestion()

        # Check if near complete
        remaining = self.progress.remaining_steps
        if len(remaining) <= 2:
            return f"""Welcome back to '{confab_name}'!

You're almost done! Just {len(remaining)} step(s) remaining:
{self._format_remaining_steps()}

{next_step}

Ready to finish up?"""

        return f"""Welcome back to '{confab_name}'!

{progress_summary}

**Suggested next step:**
{next_step}

What would you like to work on?"""

    def _format_progress_summary(self) -> str:
        """Format a summary of completed and remaining steps."""
        completed = self.progress.completed_steps
        total = self.progress.total_steps

        if not completed:
            return "**Progress:** Just getting started!"

        completed_desc = []
        for step in sorted(completed):
            if step in STEP_DESCRIPTIONS:
                completed_desc.append(f"  - Step {step}: {STEP_DESCRIPTIONS[step]}")

        return f"""**Progress:** {len(completed)}/{total} steps complete
{chr(10).join(completed_desc)}"""

    def _format_remaining_steps(self) -> str:
        """Format the remaining steps as a list."""
        remaining = self.progress.remaining_steps
        lines = []
        for step in sorted(remaining):
            if step in STEP_DESCRIPTIONS:
                lines.append(f"  - Step {step}: {STEP_DESCRIPTIONS[step]}")
        return "\n".join(lines) if lines else "All steps complete!"

    def _get_next_step_suggestion(self) -> str:
        """Get the suggestion for the next step based on current stage."""
        current_stage = self.progress.current_stage
        return STAGE_PROMPTS.get(current_stage, "What would you like to configure next?")

    def _is_question(self, text: str) -> bool:
        """Check if text contains a question."""
        # Simple heuristic: check for question marks in last few sentences
        sentences = text.split('.')
        last_sentences = sentences[-3:] if len(sentences) >= 3 else sentences
        return any('?' in s for s in last_sentences)

    def _extract_question(self, text: str) -> str:
        """Extract the question portion from text."""
        # Find sentences with question marks
        sentences = text.replace('\n', ' ').split('.')
        questions = [s.strip() for s in sentences if '?' in s]

        if questions:
            # Return the last question, truncated if needed
            last_q = questions[-1]
            if len(last_q) > 200:
                return last_q[:200] + "..."
            return last_q

        # Fallback: return last portion of text
        if len(text) > 200:
            return "..." + text[-200:]
        return text

    def get_system_context(self) -> str:
        """Build system context from GitHub files for LLM prompts."""
        parts = []

        # Add purpose if available
        if self.github_files.purpose_md:
            parts.append(f"## Agent Purpose\n{self.github_files.purpose_md}")

        # Add guardrails if available
        if self.github_files.guardrails_md:
            parts.append(f"## Agent Guardrails\n{self.github_files.guardrails_md}")

        # Add test scenarios if available
        if self.github_files.tests_md:
            parts.append(f"## Test Scenarios\n{self.github_files.tests_md}")

        # Add current progress
        parts.append(f"## Current Progress\nStage: {self.progress.current_stage}")
        parts.append(f"Completed steps: {self.progress.completed_steps}")

        return "\n\n".join(parts) if parts else "No configuration loaded yet."
