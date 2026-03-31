#!/usr/bin/env python3
"""
Branch Migration Script

Migrates existing timestamp-based branches (confab-name-timestamp) to the new
persistent branch strategy (confab-{confab_id}).

Usage:
    python scripts/migrate_branches.py [--dry-run] [--confab-id ID]

Options:
    --dry-run       Show what would be done without making changes
    --confab-id ID  Migrate only a specific confab
"""

import argparse
import asyncio
import os
import re
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.orm import Session
from database import get_db, engine
from models import Confab, GitHubAccount
from github_service import GitHubService, GitHubServiceError


class MigrationResult:
    """Result of a single confab migration."""
    def __init__(self, confab_id: int, confab_name: str):
        self.confab_id = confab_id
        self.confab_name = confab_name
        self.old_branch: Optional[str] = None
        self.new_branch: Optional[str] = None
        self.old_pr_number: Optional[int] = None
        self.new_pr_url: Optional[str] = None
        self.success: bool = False
        self.skipped: bool = False
        self.error: Optional[str] = None


async def find_timestamp_branch(
    service: GitHubService,
    confab_name: str
) -> Optional[str]:
    """
    Find an existing timestamp-based branch for a confab.

    Searches for branches matching: confab-{name}-{timestamp}
    """
    # Normalize confab name to match branch naming convention
    normalized_name = confab_name.lower().replace(" ", "-")
    pattern = re.compile(rf"^confab-{re.escape(normalized_name)}-\d+$")

    # List all branches (GitHub API doesn't support pattern matching directly)
    response = await service._request(
        "GET",
        f"/repos/{service.repo_path}/branches?per_page=100"
    )

    if response.status_code != 200:
        return None

    branches = response.json()

    for branch in branches:
        branch_name = branch["name"]
        if pattern.match(branch_name):
            return branch_name

    return None


async def get_open_pr_for_branch(
    service: GitHubService,
    branch_name: str
) -> Optional[Dict[str, Any]]:
    """Get open PR for a specific branch."""
    return await service.get_open_pr(branch_name)


async def migrate_confab(
    confab: Confab,
    github_account: GitHubAccount,
    dry_run: bool = False
) -> MigrationResult:
    """
    Migrate a single confab to the new branch strategy.

    Steps:
    1. Find existing timestamp branch
    2. Get branch HEAD SHA
    3. Create new confab-{id} branch from that SHA
    4. Close existing PR (if any)
    5. Create new PR
    6. Delete old branch
    """
    result = MigrationResult(confab.id, confab.name)

    try:
        # Initialize GitHub service
        repo_owner = github_account.selected_org or github_account.github_username
        repo_name = github_account.selected_repo

        service = GitHubService(
            access_token=github_account.access_token,
            repo_owner=repo_owner,
            repo_name=repo_name
        )

        # Check if new branch already exists
        new_branch = f"confab-{confab.id}"
        if await service.branch_exists(new_branch):
            result.skipped = True
            result.new_branch = new_branch
            result.error = f"New branch {new_branch} already exists"
            print(f"  [SKIP] Confab {confab.id} ({confab.name}): {result.error}")
            return result

        # Find existing timestamp branch
        old_branch = await find_timestamp_branch(service, confab.name)

        if not old_branch:
            result.skipped = True
            result.error = "No timestamp branch found"
            print(f"  [SKIP] Confab {confab.id} ({confab.name}): {result.error}")
            return result

        result.old_branch = old_branch
        print(f"  [FOUND] Confab {confab.id} ({confab.name}): {old_branch}")

        if dry_run:
            result.success = True
            result.new_branch = new_branch
            print(f"    [DRY-RUN] Would migrate to {new_branch}")
            return result

        # Get old branch SHA
        old_sha = await service.get_branch_sha(old_branch)

        # Check for open PRs under review
        old_pr = await get_open_pr_for_branch(service, old_branch)
        if old_pr:
            result.old_pr_number = old_pr["number"]
            print(f"    [WARNING] Found open PR #{old_pr['number']} - will be closed")

        # Create new branch from old branch HEAD
        await service.create_branch_from_sha(new_branch, old_sha)
        result.new_branch = new_branch
        print(f"    [CREATED] New branch: {new_branch}")

        # Close old PR if exists
        if old_pr:
            await service.close_pr(old_pr["number"])
            print(f"    [CLOSED] Old PR #{old_pr['number']}")

        # Create new PR
        pr = await service.create_pr(
            branch=new_branch,
            title=f"Update confab: {confab.name}",
            body=f"Migrated from branch `{old_branch}`\n\nConfab ID: {confab.id}"
        )
        result.new_pr_url = pr["html_url"]
        print(f"    [CREATED] New PR: {pr['html_url']}")

        # Delete old branch
        deleted = await service.delete_branch(old_branch)
        if deleted:
            print(f"    [DELETED] Old branch: {old_branch}")

        result.success = True

    except GitHubServiceError as e:
        result.error = str(e)
        print(f"  [ERROR] Confab {confab.id} ({confab.name}): {e}")
    except Exception as e:
        result.error = str(e)
        print(f"  [ERROR] Confab {confab.id} ({confab.name}): Unexpected error: {e}")

    return result


async def run_migration(
    db: Session,
    dry_run: bool = False,
    confab_id: Optional[int] = None
) -> List[MigrationResult]:
    """
    Run the branch migration for all confabs or a specific one.
    """
    results = []

    # Query confabs
    query = db.query(Confab).filter(Confab.github_url.isnot(None))
    if confab_id:
        query = query.filter(Confab.id == confab_id)

    confabs = query.all()

    print(f"\n{'='*60}")
    print(f"Branch Migration {'(DRY RUN)' if dry_run else ''}")
    print(f"{'='*60}")
    print(f"Found {len(confabs)} confab(s) with GitHub URLs\n")

    for confab in confabs:
        # Get GitHub account for this user
        github_account = db.query(GitHubAccount).filter(
            GitHubAccount.user_id == confab.user_id
        ).first()

        if not github_account:
            result = MigrationResult(confab.id, confab.name)
            result.skipped = True
            result.error = "No GitHub account found for user"
            results.append(result)
            print(f"  [SKIP] Confab {confab.id} ({confab.name}): {result.error}")
            continue

        result = await migrate_confab(confab, github_account, dry_run)
        results.append(result)

    return results


def print_summary(results: List[MigrationResult]) -> None:
    """Print migration summary."""
    print(f"\n{'='*60}")
    print("Migration Summary")
    print(f"{'='*60}")

    success = [r for r in results if r.success and not r.skipped]
    skipped = [r for r in results if r.skipped]
    failed = [r for r in results if not r.success and not r.skipped]

    print(f"  Successful: {len(success)}")
    print(f"  Skipped:    {len(skipped)}")
    print(f"  Failed:     {len(failed)}")

    if failed:
        print("\nFailed migrations:")
        for r in failed:
            print(f"  - Confab {r.confab_id} ({r.confab_name}): {r.error}")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate timestamp branches to confab-{id} format"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--confab-id",
        type=int,
        help="Migrate only a specific confab ID"
    )

    args = parser.parse_args()

    # Get database session
    db = next(get_db())

    try:
        results = asyncio.run(run_migration(
            db=db,
            dry_run=args.dry_run,
            confab_id=args.confab_id
        ))
        print_summary(results)

        # Exit with error code if any failures
        if any(not r.success and not r.skipped for r in results):
            sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
