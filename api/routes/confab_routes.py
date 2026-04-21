"""
Confab CRUD, export, definition-file refresh/commit, and delete routes.
"""

import re
import os
import datetime
import logging
from typing import Optional, List, Dict, Any, Tuple, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User, Confab, ConfabLearning, GitHubAccount, ConfabDocumentV2, DocumentVersion
from schemas import (
    ConfabCreate, ConfabUpdate, ConfabResponse, ConfabListItem,
    DefinitionFilesRefreshResponse, DefinitionFilesCommitRequest, DefinitionFilesCommitResponse,
)
from deps import get_current_user
from github_service import GitHubService, GitHubServiceError, FileNotFoundError as GitHubFileNotFoundError
from oasf_export import export_confab_to_oasf_yaml, generate_all_export_files
from services.hermes_webhook import notify_hermes_agents
from services.hermes_deploy import deploy_confab, undeploy_confab, get_deploy_status
from services.openwebui_knowledge import sync_knowledge_on_deploy, cleanup_knowledge_on_undeploy

logger = logging.getLogger(__name__)
router = APIRouter(tags=["confabs"])


# =============================================================================
# Utility helpers
# =============================================================================

def _slugify(value: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "untitled-confab"


def _normalize_repo_path(path: str) -> str:
    return "/".join([p for p in path.replace("\\", "/").split("/") if p not in ("", ".")])


def _is_path_within_prefix(path: str, prefix: str) -> bool:
    normalized = _normalize_repo_path(path)
    normalized_prefix = _normalize_repo_path(prefix)
    if ".." in normalized.split("/"):
        return False
    return normalized == normalized_prefix or normalized.startswith(f"{normalized_prefix}/")


def _guardrails_to_markdown(confab_name: str, guardrails: Optional[List[Dict[str, Any]]]) -> str:
    title = f"# Guardrails for {confab_name}\n\n"
    if not guardrails:
        return title + "_No guardrails defined yet._\n"
    lines = [title, "## Rules\n\n"]
    for idx, rule in enumerate(guardrails, 1):
        if not isinstance(rule, dict):
            continue
        text = str(rule.get("rule", "")).strip()
        if not text:
            continue
        lines.append(f"{idx}. {text}\n")
    return "".join(lines)


def _guardrails_from_markdown(markdown: str) -> List[Dict[str, Any]]:
    rules: List[Dict[str, Any]] = []
    lines = (markdown or "").splitlines()
    for line in lines:
        stripped = line.strip()
        numbered = re.match(r"^\d+\.\s+(.*)$", stripped)
        bulleted = re.match(r"^[-*]\s+(.*)$", stripped)
        match = numbered or bulleted
        if not match:
            continue
        text = match.group(1).strip()
        if not text or text.startswith("severity:") or text.startswith("status:"):
            continue
        rules.append({"id": f"gr-{len(rules) + 1}", "rule": text, "severity": "error", "enabled": True})
    if not rules and (markdown or "").strip():
        rules.append({"id": "gr-1", "rule": (markdown or "").strip(), "severity": "error", "enabled": True})
    return rules


def _resolve_github_target(current_user: User, confab: Confab, db: Session) -> Tuple[GitHubService, Optional[GitHubAccount], bool]:
    github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == current_user.id).first()
    if github_account:
        if not github_account.access_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub access token missing")
        repo_owner = github_account.selected_org or github_account.github_username
        repo_name = github_account.selected_repo
        service = GitHubService(access_token=github_account.access_token, repo_owner=repo_owner, repo_name=repo_name)
        return service, github_account, False
    registry_token = os.getenv("REGISTRY_GITHUB_TOKEN")
    if not registry_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Registry sync token missing. Set REGISTRY_GITHUB_TOKEN on the API server.")
    repo_owner = os.getenv("REGISTRY_REPO_OWNER", "letsconfab")
    repo_name = os.getenv("REGISTRY_REPO_NAME", "registry")
    service = GitHubService(access_token=registry_token, repo_owner=repo_owner, repo_name=repo_name)
    return service, github_account, True


def _resolve_or_set_confab_folder(confab: Confab, current_user: User, github_account: Optional[GitHubAccount], db: Session, is_registry: bool = False) -> str:
    if confab.github_path:
        if is_registry and not confab.github_path.startswith("confabs/"):
            return f"confabs/{confab.github_path}"
        return confab.github_path
    confab_slug = _slugify(confab.name)
    if is_registry:
        base_path = f"{confab_slug}-u{current_user.id}-c{confab.id}"
    else:
        base_path = f"{confab_slug}-c{confab.id}"
    confab.github_path = base_path
    db.commit()
    db.refresh(confab)
    if is_registry:
        return f"confabs/{base_path}"
    return base_path


# =============================================================================
# Confab Routes
# =============================================================================

@router.get("/confabs", response_model=List[ConfabListItem])
async def list_confabs(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    confabs = db.query(Confab).filter(Confab.user_id == current_user.id).order_by(Confab.created_at.desc()).all()
    return [ConfabListItem.model_validate(c) for c in confabs]


@router.post("/confabs", response_model=ConfabResponse)
async def create_confab(
    confab: ConfabCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_confab = Confab(
        name=confab.name,
        description=confab.description,
        user_id=current_user.id,
        status=confab.status,
        model_provider=confab.model_provider,
        model_name=confab.model_name,
        temperature=confab.temperature,
    )
    db.add(db_confab)
    db.commit()
    db.refresh(db_confab)
    return ConfabResponse.model_validate(db_confab)


@router.get("/confabs/{confab_id}", response_model=ConfabResponse)
async def get_confab(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")
    return ConfabResponse.model_validate(confab)


@router.put("/confabs/{confab_id}", response_model=ConfabResponse)
async def update_confab(
    confab_id: int,
    update: ConfabUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    # Track if this is a publish/republish event
    old_status = confab.status
    is_publish = False

    # Update fields if provided
    if update.name is not None:
        confab.name = update.name
    if update.description is not None:
        confab.description = update.description
    if update.status is not None:
        confab.status = update.status
        # Detect publish events (transition to published, or update while published)
        if update.status == "published":
            is_publish = True
    if update.purpose is not None:
        confab.purpose = update.purpose
    if update.guardrails is not None:
        confab.guardrails = [g.model_dump() for g in update.guardrails]
    if update.tests is not None:
        confab.tests = [t.model_dump() for t in update.tests]
    if update.skills is not None:
        confab.skills = update.skills
    if update.domains is not None:
        confab.domains = update.domains
    if update.model_provider is not None:
        confab.model_provider = update.model_provider
    if update.model_name is not None:
        confab.model_name = update.model_name
    if update.temperature is not None:
        confab.temperature = update.temperature

    # Increment version
    try:
        parts = confab.version.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        confab.version = ".".join(parts)
    except (ValueError, IndexError):
        confab.version = "1.0.1"

    # Regenerate OASF yaml
    confab.oasf_yaml = export_confab_to_oasf_yaml(confab, db)

    db.commit()
    db.refresh(confab)

    # Notify hermes-agents on publish/republish
    if is_publish:
        await notify_hermes_agents(confab)

    return ConfabResponse.model_validate(confab)


@router.get("/confabs/{confab_id}/export")
async def export_confab_oasf(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export a confab as OASF-compliant files.
    Returns agent.oasf.yaml, PURPOSE.md, GUARDRAILS.md, TESTS.md
    """
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    files = generate_all_export_files(confab, db)

    # Also update the cached oasf_yaml
    confab.oasf_yaml = files["agent.oasf.yaml"]
    db.commit()

    return {
        "confab_id": confab_id,
        "confab_name": confab.name,
        "version": confab.version,
        "files": files
    }


@router.post("/confabs/{confab_id}/definition-files/refresh", response_model=DefinitionFilesRefreshResponse)
async def refresh_definition_files(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Pull latest PURPOSE.md and GUARDRAILS.md from GitHub and hydrate DB fields.
    """
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    # Refresh only works if confab has been committed before (has a github_path)
    if not confab.github_path:
        return DefinitionFilesRefreshResponse(
            confab_id=confab.id,
            purpose=confab.purpose,
            guardrails_markdown=_guardrails_to_markdown(confab.name, confab.guardrails) if confab.guardrails else None,
            remote_branch=None,
            remote_source="none",
            refreshed_at=datetime.datetime.now(datetime.timezone.utc),
        )

    try:
        github_service, github_account, is_registry = _resolve_github_target(current_user, confab, db)
    except HTTPException as e:
        # GitHub not configured - return current DB state without remote sync
        return DefinitionFilesRefreshResponse(
            confab_id=confab.id,
            purpose=confab.purpose,
            guardrails_markdown=_guardrails_to_markdown(confab.name, confab.guardrails) if confab.guardrails else None,
            remote_branch=None,
            remote_source="none",
            refreshed_at=datetime.datetime.now(datetime.timezone.utc),
        )

    # Use existing path (with registry prefix if needed)
    confab_folder = confab.github_path
    if is_registry and not confab_folder.startswith("confabs/"):
        confab_folder = f"confabs/{confab_folder}"
    file_prefix = confab_folder

    purpose_path = f"{file_prefix}/PURPOSE.md"
    guardrails_path = f"{file_prefix}/GUARDRAILS.md"

    purpose_content: Optional[str] = None
    guardrails_md: Optional[str] = None
    source: Literal["default", "none"] = "none"
    source_branch: Optional[str] = None

    # Get the default branch (main) - we always commit directly to it
    try:
        default_branch = await github_service.get_default_branch()
    except GitHubServiceError:
        # Repo not accessible - return current DB state
        return DefinitionFilesRefreshResponse(
            confab_id=confab.id,
            purpose=confab.purpose,
            guardrails_markdown=_guardrails_to_markdown(confab.name, confab.guardrails) if confab.guardrails else None,
            remote_branch=None,
            remote_source="none",
            refreshed_at=datetime.datetime.now(datetime.timezone.utc),
        )

    # Look for files on the default branch only (no confab-specific branches)
    try:
        purpose_content = await github_service.get_file_contents(purpose_path, branch=default_branch)
        source = "default"
        source_branch = default_branch
    except GitHubFileNotFoundError:
        pass
    except GitHubServiceError:
        # Repo not accessible - return current DB state
        return DefinitionFilesRefreshResponse(
            confab_id=confab.id,
            purpose=confab.purpose,
            guardrails_markdown=_guardrails_to_markdown(confab.name, confab.guardrails) if confab.guardrails else None,
            remote_branch=None,
            remote_source="none",
            refreshed_at=datetime.datetime.now(datetime.timezone.utc),
        )

    try:
        guardrails_md = await github_service.get_file_contents(guardrails_path, branch=default_branch)
        source = "default"
        source_branch = default_branch
    except GitHubFileNotFoundError:
        pass
    except GitHubServiceError:
        pass  # Continue with what we have

    # Hydrate DB from remote files where available
    changed = False
    if purpose_content is not None and confab.purpose != purpose_content:
        confab.purpose = purpose_content
        changed = True
    if guardrails_md is not None:
        parsed_guardrails = _guardrails_from_markdown(guardrails_md)
        if confab.guardrails != parsed_guardrails:
            confab.guardrails = parsed_guardrails
            changed = True

    if changed:
        db.commit()
        db.refresh(confab)

    # Always re-render guardrails to normalize format (removes legacy severity/status lines)
    normalized_guardrails_md = _guardrails_to_markdown(confab.name, confab.guardrails) if confab.guardrails else guardrails_md

    return DefinitionFilesRefreshResponse(
        confab_id=confab.id,
        purpose=purpose_content,
        guardrails_markdown=normalized_guardrails_md,
        remote_branch=source_branch,
        remote_source=source,
        refreshed_at=datetime.datetime.now(datetime.timezone.utc),
    )


@router.post("/confabs/{confab_id}/definition-files/accept-and-commit", response_model=DefinitionFilesCommitResponse)
async def accept_and_commit_definition_files(
    confab_id: int,
    request: DefinitionFilesCommitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Commit PURPOSE.md and/or GUARDRAILS.md in a single batch commit.
    """
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    now = datetime.datetime.now(datetime.timezone.utc)

    # Check if there's content to save
    has_purpose = request.include_purpose and confab.purpose and confab.purpose.strip()
    has_guardrails = request.include_guardrails and confab.guardrails

    if not has_purpose and not has_guardrails:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No definition files available to commit")

    # Try to resolve GitHub target - if it fails, save locally only
    github_service = None
    branch_name = None
    confab_folder = None
    github_error_message = None

    try:
        github_service, github_account, is_registry = _resolve_github_target(current_user, confab, db)
        confab_folder = _resolve_or_set_confab_folder(confab, current_user, github_account, db, is_registry)

        # Ensure repo exists before attempting operations (auto-creates "confabs" if needed)
        repo_ok, repo_error = await github_service.ensure_repo_exists()
        if not repo_ok:
            return DefinitionFilesCommitResponse(
                confab_id=confab.id,
                branch=None,
                folder_path=None,
                committed_files=[],
                commit_sha=None,
                status="saved-locally",
                synced_at=now,
                message=repo_error or "Could not access or create GitHub repository.",
            )

        # Commit directly to the default branch (main)
        branch_name = await github_service.get_default_branch()
    except HTTPException as e:
        github_error_message = "GitHub not configured. Connect your GitHub account or ask an admin to set REGISTRY_GITHUB_TOKEN."
        github_service = None
    except GitHubServiceError as e:
        github_error_message = f"Cannot access GitHub repository: {str(e)}"
        github_service = None

    # If GitHub isn't available, return saved-locally status
    if github_service is None:
        return DefinitionFilesCommitResponse(
            confab_id=confab.id,
            branch=None,
            folder_path=None,
            committed_files=[],
            commit_sha=None,
            status="saved-locally",
            synced_at=now,
            message=github_error_message,
        )

    file_prefix = confab_folder
    candidate_files: Dict[str, str] = {}
    if has_purpose:
        candidate_files[f"{file_prefix}/PURPOSE.md"] = confab.purpose
    if has_guardrails:
        guardrails_markdown = _guardrails_to_markdown(confab.name, confab.guardrails)
        if guardrails_markdown.strip():
            candidate_files[f"{file_prefix}/GUARDRAILS.md"] = guardrails_markdown

    # Path guard enforcement
    for path in candidate_files.keys():
        if not _is_path_within_prefix(path, file_prefix):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Blocked file path outside allowed confab folder: {path}"
            )

    # Commit only files that differ from remote branch content
    changed_files: Dict[str, str] = {}
    committed_file_names: List[str] = []
    for path, content in candidate_files.items():
        remote_content: Optional[str] = None
        try:
            remote_content = await github_service.get_file_contents(path, branch=branch_name)
        except GitHubFileNotFoundError:
            remote_content = None

        if remote_content != content:
            changed_files[path] = content
            committed_file_names.append(path.split("/")[-1])

    now = datetime.datetime.now(datetime.timezone.utc)

    if not changed_files:
        confab.github_synced_at = now
        confab.github_sync_version = confab.version
        db.commit()
        db.refresh(confab)
        return DefinitionFilesCommitResponse(
            confab_id=confab.id,
            branch=branch_name,
            folder_path=confab_folder,
            committed_files=[],
            commit_sha=None,
            status="no-op",
            synced_at=now,
        )

    base_commit_message = (request.commit_message or "accept-changes-and-commit").strip()
    commit_message = f"Co Authored by foreman@letsconfab.org: {base_commit_message}"

    result = await github_service.create_or_update_files_batch(
        files=changed_files,
        branch=branch_name,
        message=commit_message
    )

    # Update sync metadata
    confab.github_synced_at = now
    confab.github_sync_version = confab.version
    db.commit()
    db.refresh(confab)

    return DefinitionFilesCommitResponse(
        confab_id=confab.id,
        branch=branch_name,
        folder_path=confab_folder,
        committed_files=committed_file_names,
        commit_sha=result.get("commit_sha"),
        status="committed",
        synced_at=now,
    )


@router.delete("/confabs/{confab_id}")
async def delete_confab(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    # Try to delete the GitHub folder if it exists
    github_folder_deleted = False
    github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == current_user.id).first()

    if github_account and github_account.access_token:
        repo_owner = github_account.selected_org or github_account.github_username
        repo_name = github_account.selected_repo
        github_service = GitHubService(
            access_token=github_account.access_token,
            repo_owner=repo_owner,
            repo_name=repo_name,
        )

        # Build list of potential folder paths to try deleting
        # - Current format: confab.github_path (e.g., "myconfab-c123")
        # - Legacy format: confabs/{name}/ (for older confabs created before path standardization)
        paths_to_try = []
        if confab.github_path:
            paths_to_try.append(confab.github_path)

        # Add legacy path format as fallback
        if confab.name:
            legacy_path = f"confabs/{_slugify(confab.name)}"
            if legacy_path not in paths_to_try:
                paths_to_try.append(legacy_path)

        for folder_path in paths_to_try:
            try:
                deleted = await github_service.delete_folder(
                    folder_path=folder_path,
                    commit_message=f"Delete confab: {confab.name}"
                )
                if deleted:
                    github_folder_deleted = True
                    logger.info(f"Deleted GitHub folder {folder_path} for confab {confab_id}")
                    break  # Successfully deleted, no need to try other paths
            except Exception as e:
                logger.warning(f"Failed to delete GitHub folder {folder_path} for confab {confab_id}: {e}")
                # Continue trying other paths

    # Delete related records before deleting confab
    # Delete document versions first (foreign key to documents)
    doc_ids = [d.id for d in db.query(ConfabDocumentV2.id).filter(ConfabDocumentV2.confab_id == confab_id).all()]
    if doc_ids:
        db.query(DocumentVersion).filter(DocumentVersion.document_id.in_(doc_ids)).delete(synchronize_session=False)
        db.query(ConfabDocumentV2).filter(ConfabDocumentV2.confab_id == confab_id).delete(synchronize_session=False)

    # Delete learnings
    db.query(ConfabLearning).filter(ConfabLearning.confab_id == confab_id).delete(synchronize_session=False)

    db.delete(confab)
    db.commit()
    return {
        "message": "Confab deleted",
        "github_folder_deleted": github_folder_deleted
    }


# =============================================================================
# Deploy / undeploy endpoints
# =============================================================================

@router.post("/confabs/{confab_id}/deploy")
async def deploy_confab_endpoint(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")
    if confab.status != "published":
        raise HTTPException(status_code=400, detail="Confab must be published before deploying")

    result = await deploy_confab(confab.name)
    if not result:
        raise HTTPException(status_code=502, detail="Failed to deploy — hermes-agents may be unavailable")

    agent_name = confab.name.lower().replace(" ", "-").replace("_", "-")
    kb_id = await sync_knowledge_on_deploy(db, confab, agent_name)

    return {"message": "Deployed", "deployment": result, "knowledge_synced": kb_id is not None}


@router.post("/confabs/{confab_id}/undeploy")
async def undeploy_confab_endpoint(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    agent_name = confab.name.lower().replace(" ", "-").replace("_", "-")
    await cleanup_knowledge_on_undeploy(agent_name)

    success = await undeploy_confab(confab.name)
    if not success:
        raise HTTPException(status_code=502, detail="Failed to undeploy — hermes-agents may be unavailable")
    return {"message": "Undeployed"}


@router.get("/confabs/{confab_id}/deploy-status")
async def deploy_status_endpoint(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    result = await get_deploy_status(confab.name)
    if result is None:
        return {"status": "not_deployed", "realizations": []}
    return result
