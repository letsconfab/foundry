"""
Unified GitHub Service for Foundry API.

This module consolidates GitHub operations from confab_manager.py (httpx) and
agent_tools.py (PyGithub) into a single async service using httpx.

Features:
- Async-compatible (httpx)
- Persistent branch strategy: confab-{confab_id}
- PR reuse logic
- Retry logic for transient failures
- Feature flag for gradual rollout
"""

import os
import httpx
import asyncio
from base64 import b64encode, b64decode
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Feature flag for gradual rollout
USE_NEW_GITHUB_SERVICE = os.getenv("USE_NEW_GITHUB_SERVICE", "false").lower() == "true"

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds


class GitHubServiceError(Exception):
    """Base exception for GitHub service errors."""
    pass


class BranchNotFoundError(GitHubServiceError):
    """Branch does not exist."""
    pass


class FileNotFoundError(GitHubServiceError):
    """File does not exist in repository."""
    pass


class PRNotFoundError(GitHubServiceError):
    """Pull request does not exist."""
    pass


class RepoNotFoundError(GitHubServiceError):
    """Repository does not exist."""
    pass


class GitHubService:
    """
    Unified async GitHub service using httpx.

    Consolidates patterns from:
    - confab_manager.py (httpx-based, async)
    - agent_tools.py (PyGithub-based, sync patterns adapted)

    Uses persistent branch strategy: confab-{confab_id}
    """

    def __init__(self, access_token: str, repo_owner: str, repo_name: str):
        """
        Initialize GitHub service.

        Args:
            access_token: GitHub personal access token
            repo_owner: Repository owner (user or org)
            repo_name: Repository name
        """
        self.access_token = access_token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.base_url = "https://api.github.com"
        self._default_branch: Optional[str] = None

    @property
    def headers(self) -> Dict[str, str]:
        """Get headers for GitHub API requests."""
        return {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {self.access_token}",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    @property
    def repo_path(self) -> str:
        """Get the repository path."""
        return f"{self.repo_owner}/{self.repo_name}"

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict] = None,
        retry: bool = True
    ) -> httpx.Response:
        """
        Make an API request with optional retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            endpoint: API endpoint (without base URL)
            json: Optional JSON body
            retry: Whether to retry on transient failures

        Returns:
            httpx.Response
        """
        url = f"{self.base_url}{endpoint}"

        for attempt in range(MAX_RETRIES if retry else 1):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=self.headers,
                        json=json
                    )

                    # Retry on rate limit or server errors
                    if response.status_code == 403 and "rate limit" in response.text.lower():
                        if attempt < MAX_RETRIES - 1:
                            logger.warning(f"Rate limited, retrying in {RETRY_DELAY}s...")
                            await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                            continue

                    if response.status_code >= 500 and attempt < MAX_RETRIES - 1:
                        logger.warning(f"Server error {response.status_code}, retrying...")
                        await asyncio.sleep(RETRY_DELAY)
                        continue

                    return response

            except httpx.RequestError as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Request error: {e}, retrying...")
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                raise

        # Should not reach here, but just in case
        raise GitHubServiceError("Max retries exceeded")

    async def get_default_branch(self) -> str:
        """Get the repository's default branch name."""
        if self._default_branch:
            return self._default_branch

        response = await self._request("GET", f"/repos/{self.repo_path}")

        if response.status_code != 200:
            raise GitHubServiceError(f"Failed to get repository info: {response.text}")

        self._default_branch = response.json()["default_branch"]
        return self._default_branch

    # ==================== Repository Operations ====================

    async def repo_exists(self) -> bool:
        """Check if the repository exists and is accessible."""
        response = await self._request(
            "GET",
            f"/repos/{self.repo_path}",
            retry=False
        )
        return response.status_code == 200

    async def create_repo(
        self,
        description: str = "Repository for confabs created via Let's Confab",
        private: bool = False
    ) -> Dict[str, Any]:
        """Create the repository if it does not exist.

        Note: Creates under the authenticated user's personal account.
        For org repos, the org admin must create the repo manually.
        """
        repo_data = {
            "name": self.repo_name,
            "description": description,
            "private": private,
            "auto_init": True,
        }

        response = await self._request("POST", "/user/repos", json=repo_data)

        if response.status_code == 201:
            logger.info(f"Created repository {self.repo_path}")
            return response.json()

        # Handle concurrent creation race condition (422 = already exists)
        if response.status_code == 422:
            error_data = response.json()
            if "already exists" in str(error_data).lower():
                logger.info(f"Repository {self.repo_name} already exists (concurrent creation)")
                return {"name": self.repo_name, "full_name": self.repo_path}

        error_data = response.json()
        raise GitHubServiceError(
            f"Failed to create repository: {error_data.get('message', 'Unknown error')}"
        )

    async def ensure_repo_exists(
        self,
        description: str = "Repository for confabs created via Let's Confab",
        private: bool = False,
        auto_create_only_default: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """Ensure the repository exists, creating it if necessary.

        Args:
            description: Repository description (used if creating)
            private: Whether new repo should be private
            auto_create_only_default: If True, only auto-create if repo_name is "confabs"

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        if await self.repo_exists():
            return True, None

        # Only auto-create the default "confabs" repo
        if auto_create_only_default and self.repo_name != "confabs":
            return False, f"Repository '{self.repo_name}' not found. Please create it on GitHub or use the default 'confabs' repository."

        logger.info(f"Repository {self.repo_path} not found, attempting to create")
        try:
            await self.create_repo(description=description, private=private)
            # Wait briefly for GitHub to propagate the repo
            await asyncio.sleep(1.0)
            return True, None
        except GitHubServiceError as e:
            error_msg = str(e)
            logger.warning(f"Failed to create repository {self.repo_path}: {error_msg}")
            return False, error_msg

    # ==================== Branch Operations ====================

    async def branch_exists(self, branch_name: str) -> bool:
        """Check if a branch exists."""
        response = await self._request(
            "GET",
            f"/repos/{self.repo_path}/git/ref/heads/{branch_name}",
            retry=False
        )
        return response.status_code == 200

    async def get_or_create_branch(self, confab_id_or_branch: Union[int, str]) -> str:
        """
        Get or create a confab-specific branch.

        Uses persistent branch strategy: confab-{confab_id}.
        If a branch name is provided directly, it will be used as-is.

        Args:
            confab_id_or_branch: Confab ID or explicit branch name

        Returns:
            Branch name
        """
        if isinstance(confab_id_or_branch, str):
            branch_name = confab_id_or_branch
        else:
            branch_name = f"confab-{confab_id_or_branch}"

        if await self.branch_exists(branch_name):
            logger.info(f"Branch {branch_name} already exists")
            return branch_name

        # Get default branch SHA
        default_branch = await self.get_default_branch()
        response = await self._request(
            "GET",
            f"/repos/{self.repo_path}/git/ref/heads/{default_branch}"
        )

        if response.status_code != 200:
            raise GitHubServiceError(f"Failed to get default branch ref: {response.text}")

        base_sha = response.json()["object"]["sha"]

        # Create new branch
        response = await self._request(
            "POST",
            f"/repos/{self.repo_path}/git/refs",
            json={
                "ref": f"refs/heads/{branch_name}",
                "sha": base_sha
            }
        )

        if response.status_code != 201:
            raise GitHubServiceError(f"Failed to create branch: {response.text}")

        logger.info(f"Created branch {branch_name} from {default_branch}")
        return branch_name

    async def create_branch_from_sha(self, branch_name: str, source_sha: str) -> str:
        """
        Create a branch from a specific SHA.

        Useful for branch migration (creating from old branch HEAD).

        Args:
            branch_name: Name of the new branch
            source_sha: SHA to create branch from

        Returns:
            Branch name
        """
        response = await self._request(
            "POST",
            f"/repos/{self.repo_path}/git/refs",
            json={
                "ref": f"refs/heads/{branch_name}",
                "sha": source_sha
            }
        )

        if response.status_code != 201:
            raise GitHubServiceError(f"Failed to create branch from SHA: {response.text}")

        logger.info(f"Created branch {branch_name} from SHA {source_sha[:8]}")
        return branch_name

    async def get_branch_sha(self, branch_name: str) -> str:
        """Get the HEAD SHA of a branch."""
        response = await self._request(
            "GET",
            f"/repos/{self.repo_path}/git/ref/heads/{branch_name}"
        )

        if response.status_code == 404:
            raise BranchNotFoundError(f"Branch {branch_name} not found")

        if response.status_code != 200:
            raise GitHubServiceError(f"Failed to get branch SHA: {response.text}")

        return response.json()["object"]["sha"]

    async def delete_branch(self, branch_name: str) -> bool:
        """
        Delete a branch.

        Args:
            branch_name: Branch to delete

        Returns:
            True if deleted, False if not found
        """
        response = await self._request(
            "DELETE",
            f"/repos/{self.repo_path}/git/refs/heads/{branch_name}"
        )

        if response.status_code == 204:
            logger.info(f"Deleted branch {branch_name}")
            return True
        elif response.status_code == 422:  # Reference does not exist
            return False
        else:
            raise GitHubServiceError(f"Failed to delete branch: {response.text}")

    # ==================== File Operations ====================

    async def get_file_contents(self, path: str, branch: Optional[str] = None) -> str:
        """
        Get file contents from repository.

        Args:
            path: File path in repository
            branch: Branch name (default: default branch)

        Returns:
            File contents as string
        """
        if branch is None:
            branch = await self.get_default_branch()

        response = await self._request(
            "GET",
            f"/repos/{self.repo_path}/contents/{path}?ref={branch}"
        )

        if response.status_code == 404:
            raise FileNotFoundError(f"File {path} not found on branch {branch}")

        if response.status_code != 200:
            raise GitHubServiceError(f"Failed to get file contents: {response.text}")

        data = response.json()

        if data.get("type") != "file":
            raise GitHubServiceError(f"Path {path} is not a file")

        content = b64decode(data["content"]).decode("utf-8")
        return content

    async def get_file_sha(self, path: str, branch: str) -> Optional[str]:
        """
        Get the SHA of a file (needed for updates).

        Args:
            path: File path
            branch: Branch name

        Returns:
            File SHA or None if file doesn't exist
        """
        response = await self._request(
            "GET",
            f"/repos/{self.repo_path}/contents/{path}?ref={branch}",
            retry=False
        )

        if response.status_code == 404:
            return None

        if response.status_code != 200:
            raise GitHubServiceError(f"Failed to get file SHA: {response.text}")

        return response.json().get("sha")

    async def create_or_update_file(
        self,
        path: str,
        content: str,
        branch: str,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create or update a file in the repository.

        Args:
            path: File path in repository
            content: File content
            branch: Branch name
            message: Commit message (auto-generated if not provided)

        Returns:
            API response with commit info
        """
        # Get existing file SHA if it exists
        existing_sha = await self.get_file_sha(path, branch)

        if message is None:
            action = "Update" if existing_sha else "Create"
            message = f"{action} {path}"

        file_data = {
            "message": message,
            "content": b64encode(content.encode()).decode(),
            "branch": branch
        }

        if existing_sha:
            file_data["sha"] = existing_sha

        response = await self._request(
            "PUT",
            f"/repos/{self.repo_path}/contents/{path}",
            json=file_data
        )

        if response.status_code not in [200, 201]:
            raise GitHubServiceError(f"Failed to create/update file: {response.text}")

        logger.info(f"{'Updated' if existing_sha else 'Created'} file {path} on {branch}")
        return response.json()

    async def create_or_update_files_batch(
        self,
        files: Dict[str, str],
        branch: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Create or update multiple files in a single commit on a branch.

        Args:
            files: Mapping of file_path -> content
            branch: Branch name
            message: Commit message

        Returns:
            Dict with commit and ref update information
        """
        if not files:
            raise GitHubServiceError("No files provided for batch commit")

        # 1) Resolve branch HEAD commit SHA
        ref_resp = await self._request(
            "GET",
            f"/repos/{self.repo_path}/git/ref/heads/{branch}"
        )
        if ref_resp.status_code != 200:
            raise GitHubServiceError(f"Failed to read branch ref: {ref_resp.text}")
        head_sha = ref_resp.json()["object"]["sha"]

        # 2) Get base tree SHA from current HEAD commit
        commit_resp = await self._request(
            "GET",
            f"/repos/{self.repo_path}/git/commits/{head_sha}"
        )
        if commit_resp.status_code != 200:
            raise GitHubServiceError(f"Failed to read current commit: {commit_resp.text}")
        base_tree_sha = commit_resp.json()["tree"]["sha"]

        # 3) Create blobs for each file
        tree_entries: List[Dict[str, str]] = []
        for path, content in files.items():
            blob_resp = await self._request(
                "POST",
                f"/repos/{self.repo_path}/git/blobs",
                json={"content": content, "encoding": "utf-8"}
            )
            if blob_resp.status_code != 201:
                raise GitHubServiceError(f"Failed to create blob for {path}: {blob_resp.text}")
            blob_sha = blob_resp.json()["sha"]
            tree_entries.append({
                "path": path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha,
            })

        # 4) Create a new tree from base tree + updated file blobs
        tree_resp = await self._request(
            "POST",
            f"/repos/{self.repo_path}/git/trees",
            json={"base_tree": base_tree_sha, "tree": tree_entries}
        )
        if tree_resp.status_code != 201:
            raise GitHubServiceError(f"Failed to create tree: {tree_resp.text}")
        new_tree_sha = tree_resp.json()["sha"]

        # 5) Create commit
        new_commit_resp = await self._request(
            "POST",
            f"/repos/{self.repo_path}/git/commits",
            json={
                "message": message,
                "tree": new_tree_sha,
                "parents": [head_sha],
            }
        )
        if new_commit_resp.status_code != 201:
            raise GitHubServiceError(f"Failed to create commit: {new_commit_resp.text}")
        new_commit = new_commit_resp.json()
        new_commit_sha = new_commit["sha"]

        # 6) Move branch ref to new commit
        update_ref_resp = await self._request(
            "PATCH",
            f"/repos/{self.repo_path}/git/refs/heads/{branch}",
            json={"sha": new_commit_sha, "force": False}
        )
        if update_ref_resp.status_code != 200:
            raise GitHubServiceError(f"Failed to update branch ref: {update_ref_resp.text}")

        logger.info(f"Created batch commit on {branch}: {new_commit_sha}")
        return {
            "commit_sha": new_commit_sha,
            "commit_url": new_commit.get("url"),
            "files_count": len(files),
            "branch": branch,
        }

    async def list_directory(self, path: str, branch: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List files in a directory.

        Args:
            path: Directory path
            branch: Branch name (default: default branch)

        Returns:
            List of file/directory info dicts
        """
        if branch is None:
            branch = await self.get_default_branch()

        response = await self._request(
            "GET",
            f"/repos/{self.repo_path}/contents/{path}?ref={branch}"
        )

        if response.status_code == 404:
            return []  # Directory doesn't exist

        if response.status_code != 200:
            raise GitHubServiceError(f"Failed to list directory: {response.text}")

        data = response.json()

        # GitHub returns a list for directories, a dict for files
        if isinstance(data, dict):
            raise GitHubServiceError(f"Path {path} is a file, not a directory")

        return data

    # ==================== PR Operations ====================

    async def get_open_pr(self, branch: str) -> Optional[Dict[str, Any]]:
        """
        Get open PR for a branch.

        Args:
            branch: Branch name

        Returns:
            PR info dict or None if no open PR
        """
        response = await self._request(
            "GET",
            f"/repos/{self.repo_path}/pulls?state=open&head={self.repo_owner}:{branch}"
        )

        if response.status_code != 200:
            raise GitHubServiceError(f"Failed to get PRs: {response.text}")

        prs = response.json()

        # Find PR matching our branch
        for pr in prs:
            if pr["head"]["ref"] == branch:
                return pr

        return None

    async def create_pr(
        self,
        branch: str,
        title: str,
        body: str,
        base: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new pull request.

        Args:
            branch: Head branch
            title: PR title
            body: PR body/description
            base: Base branch (default: default branch)

        Returns:
            PR info dict
        """
        if base is None:
            base = await self.get_default_branch()

        # Check if PR already exists
        existing_pr = await self.get_open_pr(branch)
        if existing_pr:
            logger.info(f"PR already exists: #{existing_pr['number']}")
            return existing_pr

        response = await self._request(
            "POST",
            f"/repos/{self.repo_path}/pulls",
            json={
                "title": title,
                "body": body,
                "head": branch,
                "base": base
            }
        )

        if response.status_code != 201:
            raise GitHubServiceError(f"Failed to create PR: {response.text}")

        pr = response.json()
        logger.info(f"Created PR #{pr['number']}")
        return pr

    async def close_pr(self, pr_number: int) -> bool:
        """
        Close a pull request.

        Args:
            pr_number: PR number

        Returns:
            True if closed successfully
        """
        response = await self._request(
            "PATCH",
            f"/repos/{self.repo_path}/pulls/{pr_number}",
            json={"state": "closed"}
        )

        if response.status_code == 200:
            logger.info(f"Closed PR #{pr_number}")
            return True
        elif response.status_code == 404:
            raise PRNotFoundError(f"PR #{pr_number} not found")
        else:
            raise GitHubServiceError(f"Failed to close PR: {response.text}")

    async def merge_pr(self, pr_number: int, merge_method: str = "merge") -> bool:
        """
        Merge a pull request.

        Args:
            pr_number: PR number
            merge_method: "merge", "squash", or "rebase"

        Returns:
            True if merged successfully
        """
        response = await self._request(
            "PUT",
            f"/repos/{self.repo_path}/pulls/{pr_number}/merge",
            json={"merge_method": merge_method}
        )

        if response.status_code == 200:
            logger.info(f"Merged PR #{pr_number}")
            return True
        elif response.status_code == 405:
            # Not mergeable
            logger.warning(f"PR #{pr_number} is not mergeable")
            return False
        elif response.status_code == 404:
            raise PRNotFoundError(f"PR #{pr_number} not found")
        else:
            raise GitHubServiceError(f"Failed to merge PR: {response.text}")

    async def is_pr_mergeable(self, pr_number: int) -> bool:
        """Check if a PR is mergeable."""
        response = await self._request(
            "GET",
            f"/repos/{self.repo_path}/pulls/{pr_number}"
        )

        if response.status_code == 404:
            raise PRNotFoundError(f"PR #{pr_number} not found")

        if response.status_code != 200:
            raise GitHubServiceError(f"Failed to get PR: {response.text}")

        pr = response.json()
        return pr.get("mergeable", False)

    # ==================== High-Level Operations ====================

    async def commit_confab_file(
        self,
        confab_name: str,
        file_name: str,
        content: str,
        confab_id: int,
        message: Optional[str] = None
    ) -> str:
        """
        Commit a file to the confab directory and ensure PR exists.

        High-level operation that:
        1. Ensures branch exists
        2. Creates/updates file
        3. Ensures PR exists

        Args:
            confab_name: Confab name (for directory path)
            file_name: File name (e.g., "PURPOSE.md")
            content: File content
            confab_id: Confab ID (for branch naming)
            message: Optional commit message

        Returns:
            PR URL
        """
        # Ensure branch exists
        branch = await self.get_or_create_branch(confab_id)

        # Build file path
        confab_dir = confab_name.lower().replace(" ", "-")
        file_path = f"confabs/{confab_dir}/{file_name}"

        # Create/update file
        if message is None:
            message = f"Update {file_name} for confab {confab_name}"

        await self.create_or_update_file(file_path, content, branch, message)

        # Ensure PR exists
        pr = await self.create_pr(
            branch=branch,
            title=f"Update confab: {confab_name}",
            body=f"Automated update for confab {confab_name} (ID: {confab_id})"
        )

        return pr["html_url"]

    async def create_confab_files(
        self,
        confab_name: str,
        confab_data: Dict[str, Any],
        confab_id: int
    ) -> str:
        """
        Create all confab files (Confab.toml, PURPOSE.md, GUARDRAILS.md, TESTS.md).

        Args:
            confab_name: Confab name
            confab_data: Confab data dict
            confab_id: Confab ID

        Returns:
            PR URL
        """
        # Ensure branch exists
        branch = await self.get_or_create_branch(confab_id)

        confab_dir = confab_name.lower().replace(" ", "-")
        base_path = f"confabs/{confab_dir}"

        # Prepare TOML content using string formatting (consistent with confab_manager.py)
        confab_toml = f"""[confab]
name = "{confab_name}"
description = "{confab_data.get('description', '')}"
version = "1.0.0"
created_at = "{datetime.now().isoformat()}"
status = "{confab_data.get('status', 'building')}"

[metadata]
author = "Let's Confab"
license = "MIT"
"""

        # Prepare files
        files = {
            "Confab.toml": confab_toml,
            "PURPOSE.md": f"# Purpose: {confab_name}\n\n{confab_data.get('purpose', 'Define the purpose of this confab.')}\n",
            "GUARDRAILS.md": f"# Guardrails\n\n{confab_data.get('guardrails', 'Define safety guardrails for this confab.')}\n",
            "TESTS.md": f"# Test Scenarios\n\n{confab_data.get('tests', 'Define test scenarios for this confab.')}\n"
        }

        # Create each file
        for file_name, content in files.items():
            file_path = f"{base_path}/{file_name}"
            await self.create_or_update_file(
                file_path,
                content,
                branch,
                f"Add {file_name} for confab {confab_name}"
            )

        # Create PR
        pr = await self.create_pr(
            branch=branch,
            title=f"Add confab: {confab_name}",
            body=f"Automated confab creation for {confab_name}\n\n{confab_data.get('description', '')}"
        )

        return pr["html_url"]


# ==================== Module-level helper functions ====================

async def create_confab_in_github(
    confab_name: str,
    confab_data: Dict[str, Any],
    repo_owner: str,
    repo_name: str,
    access_token: Optional[str] = None,
    confab_id: Optional[int] = None
) -> str:
    """
    Create a new confab in GitHub repository.

    Drop-in replacement for confab_manager.create_confab_in_github().

    Args:
        confab_name: Name of the confab
        confab_data: Confab data dictionary
        repo_owner: Repository owner
        repo_name: Repository name
        access_token: GitHub access token
        confab_id: Confab ID (required for new branch strategy)

    Returns:
        PR URL
    """
    if not access_token:
        raise GitHubServiceError("GitHub access token required")

    if confab_id is None:
        # Fallback for backward compatibility - use timestamp
        confab_id = int(datetime.now().timestamp())
        logger.warning(f"No confab_id provided, using timestamp: {confab_id}")

    service = GitHubService(access_token, repo_owner, repo_name)
    return await service.create_confab_files(confab_name, confab_data, confab_id)


async def update_confab_in_github(
    confab_name: str,
    confab_data: Dict[str, Any],
    github_url: str,
    access_token: str,
    confab_id: Optional[int] = None
) -> str:
    """
    Update an existing confab in GitHub repository.

    Drop-in replacement for confab_manager.update_confab_in_github().
    """
    # Extract repo info from GitHub URL
    parts = github_url.split("/")
    repo_owner = parts[3]
    repo_name = parts[4]

    if confab_id is None:
        # Try to extract from URL or use timestamp
        confab_id = int(datetime.now().timestamp())
        logger.warning(f"No confab_id provided, using timestamp: {confab_id}")

    service = GitHubService(access_token, repo_owner, repo_name)
    return await service.create_confab_files(confab_name, confab_data, confab_id)
