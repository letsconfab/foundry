"""Model-router registration helpers.

The first-pass router discovers running deployments from the database, so
registration is persisted as a deployment flag for status visibility.
"""

import os

OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", "http://localhost:3001").rstrip("/")
HERMES_MODEL_ROUTER_URL = os.getenv("HERMES_MODEL_ROUTER_URL", "http://localhost:8010").rstrip("/")


async def register_deployment_model(deployment) -> dict:
    deployment.openwebui_model_id = deployment.model_id
    deployment.router_registered = True
    return {
        "model_id": deployment.model_id,
        "router_url": HERMES_MODEL_ROUTER_URL,
        "openwebui_url": OPENWEBUI_URL,
    }


async def unregister_deployment_model(deployment) -> bool:
    deployment.router_registered = False
    return True
