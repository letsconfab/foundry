"""Deploy, undeploy, and status workflows for Hermes profile runtimes."""

import datetime as dt
import hashlib
import os
import secrets

from sqlalchemy.orm import Session

from models import Confab, ConfabDeployment
from services.deployment_naming import (
    container_name,
    deployment_model_id,
    profile_name,
    rag_workspace,
)
from services.hermes_profile import write_profile_files
from services.hermes_runtime import (
    allocate_port,
    create_or_replace_container,
    get_runtime_health,
    remove_container,
    start_container,
    stop_container,
    wait_for_runtime_healthy,
)
from services.model_router import OPENWEBUI_URL, register_deployment_model, unregister_deployment_model
from services.rag_sync import sync_documents_to_raganything

_LOCAL_PROFILE_DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "hermes-profiles")
)
HERMES_PROFILE_DATA_DIR = os.getenv("HERMES_PROFILE_DATA_DIR", _LOCAL_PROFILE_DATA_DIR)
HERMES_PROFILE_CONTAINER_PREFIX = os.getenv("HERMES_PROFILE_CONTAINER_PREFIX", "hermes-confab")


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _deployment_payload(deployment: ConfabDeployment) -> dict:
    return {
        "status": deployment.status,
        "runtime": deployment.runtime,
        "profile_name": deployment.profile_name,
        "model_id": deployment.model_id,
        "container_name": deployment.container_name,
        "api_base_url": deployment.api_base_url_external,
        "openwebui_url": OPENWEBUI_URL,
        "rag_workspace": deployment.rag_workspace,
    }


async def get_or_create_deployment(db: Session, confab: Confab) -> tuple[ConfabDeployment, str]:
    model_id = deployment_model_id(confab)
    deployment = db.query(ConfabDeployment).filter(ConfabDeployment.confab_id == confab.id).first()
    api_key = f"{os.getenv('HERMES_PROFILE_API_KEY_PREFIX', 'foundry-confab')}-{secrets.token_urlsafe(24)}"
    if deployment:
        deployment.profile_name = profile_name(confab)
        deployment.model_id = model_id
        deployment.container_name = container_name(confab)
        deployment.profile_host_path = os.path.join(HERMES_PROFILE_DATA_DIR, deployment.profile_name)
        deployment.rag_workspace = rag_workspace(confab)
        deployment.rag_prefix = f"{deployment.rag_workspace}/"
        deployment.api_base_url_external = f"http://localhost:{deployment.api_port}/v1"
        deployment.api_base_url_internal = f"http://{deployment.container_name}:8642/v1"
        deployment.api_server_key_hash = _hash_key(api_key)
        return deployment, api_key

    port = await allocate_port(db)
    profile = profile_name(confab)
    deployment = ConfabDeployment(
        confab_id=confab.id,
        user_id=confab.user_id,
        runtime="hermes_profile",
        status="provisioning",
        profile_name=profile,
        model_id=model_id,
        container_name=container_name(confab),
        profile_host_path=os.path.join(HERMES_PROFILE_DATA_DIR, profile),
        api_port=port,
        api_server_key_hash=_hash_key(api_key),
        api_base_url_external=f"http://localhost:{port}/v1",
        api_base_url_internal=f"http://{container_name(confab)}:8642/v1",
        rag_workspace=rag_workspace(confab),
        rag_prefix=f"{rag_workspace(confab)}/",
        llm_provider=confab.model_provider,
        llm_model=confab.model_name,
        llm_config_source="platform_default",
    )
    db.add(deployment)
    return deployment, api_key


async def deploy_confab(db: Session, confab: Confab) -> dict:
    deployment, api_key = await get_or_create_deployment(db, confab)
    try:
        deployment.status = "syncing_knowledge"
        deployment.last_error = None
        db.commit()

        rag_result = await sync_documents_to_raganything(db, confab)
        deployment.last_sync_result = rag_result
        deployment.status = "rendering_profile"
        db.commit()

        await write_profile_files(confab, deployment, api_key)
        deployment.status = "starting_runtime"
        db.commit()

        created = await create_or_replace_container(deployment)
        if not created.ok:
            raise RuntimeError(created.detail or "Failed to create Hermes container")
        started = await start_container(deployment)
        if not started.ok:
            raise RuntimeError(started.detail or "Failed to start Hermes container")
        health = await wait_for_runtime_healthy(deployment)

        deployment.status = "registering_model"
        deployment.last_health = health
        db.commit()

        await register_deployment_model(deployment)
        deployment.status = "running"
        deployment.status_detail = None
        deployment.deployed_at = dt.datetime.now(dt.timezone.utc)
        deployment.stopped_at = None
        db.commit()
        db.refresh(deployment)

        return {
            "message": "Deployed",
            "deployment": _deployment_payload(deployment),
            "knowledge_synced": rag_result["indexed"] or rag_result["classical_indexed"],
            "rag_indexed": rag_result["uploaded"],
            "rag_workspace": rag_result["workspace"],
            "rag_errors": rag_result["errors"],
        }
    except Exception as e:
        deployment.status = "failed"
        deployment.last_error = str(e)
        deployment.status_detail = str(e)
        db.commit()
        raise


async def undeploy_confab(db: Session, confab: Confab) -> dict:
    deployment = db.query(ConfabDeployment).filter(ConfabDeployment.confab_id == confab.id).first()
    if not deployment:
        return {
            "message": "Undeployed",
            "deployment": {
                "status": "stopped",
                "profile_name": None,
                "model_id": None,
                "profile_preserved": True,
                "rag_workspace": rag_workspace(confab),
            },
        }
    deployment.status = "deleting"
    db.commit()
    await unregister_deployment_model(deployment)
    await stop_container(deployment)
    await remove_container(deployment)
    deployment.status = "stopped"
    deployment.stopped_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    return {
        "message": "Undeployed",
        "deployment": {
            "status": "stopped",
            "profile_name": deployment.profile_name,
            "model_id": deployment.model_id,
            "profile_preserved": True,
            "rag_workspace": deployment.rag_workspace,
        },
    }


async def get_deploy_status(db: Session, confab: Confab) -> dict:
    deployment = db.query(ConfabDeployment).filter(ConfabDeployment.confab_id == confab.id).first()
    if not deployment:
        return {
            "status": "not_deployed",
            "runtime": "hermes_profile",
            "model_id": None,
            "rag_workspace": rag_workspace(confab),
        }
    health = deployment.last_health
    if deployment.status == "running":
        latest_health = await get_runtime_health(deployment)
        if latest_health:
            health = latest_health
            deployment.last_health = latest_health
            db.commit()
    sync = deployment.last_sync_result or {}
    return {
        "status": deployment.status,
        "runtime": deployment.runtime,
        "profile_name": deployment.profile_name,
        "model_id": deployment.model_id,
        "container_name": deployment.container_name,
        "api_base_url": deployment.api_base_url_external,
        "openwebui_url": OPENWEBUI_URL,
        "rag_workspace": deployment.rag_workspace,
        "runtime_health": health,
        "knowledge": {
            "uploaded": sync.get("uploaded", 0),
            "indexed": sync.get("indexed", False),
            "classical_indexed": sync.get("classical_indexed", False),
            "errors": sync.get("errors", []),
        },
        "last_error": deployment.last_error,
    }
