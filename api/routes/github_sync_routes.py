import os
import re
import datetime
import logging
from typing import Optional, List, Dict, Any, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User, Confab, Thread, GitHubAccount
from schemas import (
    SystemStatusResponse, GitHubSyncRequest, GitHubSyncResponse,
    UserListItem,
)
from deps import get_current_user
from github_service import GitHubService, GitHubServiceError
from oasf_export import generate_all_export_files
from routes.confab_routes import _slugify, _resolve_github_target, _resolve_or_set_confab_folder, _is_path_within_prefix

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])


@router.get("/users", response_model=List[UserListItem])
async def list_users(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.name).all()
    return [UserListItem.model_validate(u) for u in users]


@router.get("/admin/system-status", response_model=SystemStatusResponse)
async def get_system_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total_users = db.query(User).count()
    total_confabs = db.query(Confab).count()
    active_threads = db.query(Thread).count()

    return SystemStatusResponse(
        database="healthy",
        llm_service="healthy",
        github_service="healthy",
        active_threads=active_threads,
        total_confabs=total_confabs,
        total_users=total_users,
    )


@router.post("/admin/sync-to-github", response_model=GitHubSyncResponse)
async def sync_to_github(
    request: GitHubSyncRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Confab).filter(Confab.user_id == current_user.id)
    if request.confab_ids:
        query = query.filter(Confab.id.in_(request.confab_ids))
    confabs = query.all()

    synced = 0
    failed = 0
    errors = []

    for confab in confabs:
        try:
            github_service, github_account, is_registry = _resolve_github_target(current_user, confab, db)
            files = generate_all_export_files(confab, db)
            confab_folder = _resolve_or_set_confab_folder(confab, current_user, github_account, db, is_registry)
            file_prefix = confab_folder
            default_branch = await github_service.get_default_branch()

            batch_files: Dict[str, str] = {}
            for filename, content in files.items():
                file_path = f"{file_prefix}/{filename}"
                if not _is_path_within_prefix(file_path, file_prefix):
                    raise GitHubServiceError(f"Blocked file path outside allowed prefix: {file_path}")
                batch_files[file_path] = content

            await github_service.create_or_update_files_batch(
                files=batch_files, branch=default_branch,
                message=f"Sync confab {confab.name} (v{confab.version})"
            )

            confab.oasf_yaml = files["agent.oasf.yaml"]
            confab.github_path = confab_folder
            confab.github_synced_at = datetime.datetime.now(datetime.timezone.utc)
            confab.github_sync_version = confab.version
            synced += 1
            logger.info(f"Synced confab {confab.id} to GitHub: {confab_folder}")

        except Exception as e:
            failed += 1
            errors.append({"confab_id": confab.id, "error": str(e)})
            logger.error(f"Failed to sync confab {confab.id}: {e}")

    db.commit()
    return GitHubSyncResponse(synced_count=synced, failed_count=failed, errors=errors)
