"""OpenAI-compatible proxy to running confab profile runtimes."""

import json
import logging
import os

import aiohttp
from fastapi import HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from models import ConfabDeployment
from services.hermes_runtime import load_profile_api_key
from services.rag_sources import retrieve_rag_sources

logger = logging.getLogger(__name__)

HERMES_MODEL_ROUTER_API_KEY = os.getenv("HERMES_MODEL_ROUTER_API_KEY", "")
HERMES_MODEL_ROUTER_LOCAL_DEV = os.getenv("HERMES_MODEL_ROUTER_LOCAL_DEV", "false").lower() == "true"
HERMES_MODEL_ROUTER_PROXY_BASE = os.getenv("HERMES_MODEL_ROUTER_PROXY_BASE", "external").lower()


def authorize_router(authorization: str | None) -> None:
    if HERMES_MODEL_ROUTER_LOCAL_DEV:
        return
    if not HERMES_MODEL_ROUTER_API_KEY:
        raise HTTPException(status_code=503, detail="Model router API key is not configured")
    expected = f"Bearer {HERMES_MODEL_ROUTER_API_KEY}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def openai_error(message: str, status_code: int, code: str = "not_found") -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "type": "invalid_request_error",
                "code": code,
            }
        },
    )


def list_running_models(db: Session) -> dict:
    deployments = (
        db.query(ConfabDeployment)
        .filter(ConfabDeployment.status == "running")
        .order_by(ConfabDeployment.id.asc())
        .all()
    )
    return {
        "object": "list",
        "data": [
            {
                "id": deployment.model_id,
                "object": "model",
                "created": int(deployment.created_at.timestamp()) if deployment.created_at else 0,
                "owned_by": "foundry",
            }
            for deployment in deployments
        ],
    }


def _grounding_instruction(deployment: ConfabDeployment, has_source_context: bool = False) -> str:
    context_rule = (
        "Foundry has supplied retrieved RAGAnything source context in this request. Use that supplied context "
        "first as the primary grounding basis for factual claims. If the supplied context is insufficient, you "
        "may call `mcp_raganything_knowledge_query_knowledge_base` before answering. "
        if has_source_context
        else "For any question that may depend on uploaded confab documents, approved learnings, or the confab's "
        "domain knowledge, you must call `mcp_raganything_knowledge_query_knowledge_base` before answering. "
    )
    return (
        "Foundry router grounding instruction for this request: answer as the deployed confab model. "
        f"The deployed RAGAnything workspace is `{deployment.rag_workspace}`. "
        f"{context_rule}"
        "Use `working_dir` exactly "
        f"`{deployment.rag_workspace}`, use the user's current question as `query`, use `mode` `naive`, and "
        "`top_k` 10. If the result is empty or weak, retry the same knowledge tool with `mode` `hybrid+` and "
        "`top_k` 10. Do not call `mcp_raganything_classical_classical_query` as the first search. Do not treat "
        "a previous assistant message or one empty classical search result as evidence that deployed knowledge "
        "is absent. If prior chat history says the knowledge base had no relevant material, ignore that prior "
        "claim and search the knowledge tool again for the current user request."
    )


def _last_user_content(body: dict) -> str:
    for message in reversed(body.get("messages") or []):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            return "\n".join(part for part in parts if part.strip())
    return ""


def _body_with_grounding_instruction(
    deployment: ConfabDeployment,
    body: dict,
    source_context: str = "",
) -> dict:
    routed = dict(body)
    messages = list(routed.get("messages") or [])
    content = _grounding_instruction(deployment, bool(source_context))
    if source_context:
        content = (
            f"{content}\n\n"
            "Foundry retrieved the following RAGAnything source context for this user request.\n"
            "Use it as the primary grounding basis for factual claims. If the context is insufficient,\n"
            "say so clearly instead of inventing support.\n\n"
            f"{source_context}"
        )
    instruction = {"role": "system", "content": content}
    if not messages:
        routed["messages"] = [instruction]
        return routed

    last_user_index = None
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].get("role") == "user":
            last_user_index = index
            break

    if last_user_index is None:
        messages.insert(0, instruction)
    else:
        messages.insert(last_user_index, instruction)
    routed["messages"] = messages
    return routed


async def _retrieve_source_basis(deployment: ConfabDeployment, body: dict) -> tuple[list[dict], str]:
    try:
        return await retrieve_rag_sources(deployment.rag_workspace, _last_user_content(body))
    except Exception as e:
        logger.warning(
            "RAGAnything source retrieval failed for model %s workspace %s: %s",
            deployment.model_id,
            deployment.rag_workspace,
            e,
        )
        return [], ""


async def proxy_chat_completion(db: Session, body: dict):
    model_id = body.get("model")
    if not model_id:
        return openai_error("Missing required field: model", 400, "missing_model")
    deployment = (
        db.query(ConfabDeployment)
        .filter(ConfabDeployment.status == "running", ConfabDeployment.model_id == model_id)
        .first()
    )
    if not deployment:
        return openai_error(f"Model not found: {model_id}", 404, "model_not_found")
    api_key = load_profile_api_key(deployment)
    if not api_key:
        return openai_error("Deployment API key is unavailable", 503, "deployment_key_unavailable")

    base_url = (
        deployment.api_base_url_internal
        if HERMES_MODEL_ROUTER_PROXY_BASE == "internal"
        else deployment.api_base_url_external
    )
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    timeout = aiohttp.ClientTimeout(total=None if body.get("stream") else 120)
    sources, source_context = await _retrieve_source_basis(deployment, body)
    routed_body = _body_with_grounding_instruction(deployment, body, source_context)

    if body.get("stream"):
        async def stream():
            for source in sources:
                yield f"data: {json.dumps({'event': {'type': 'source', 'data': source}})}\n\n".encode()
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=routed_body) as resp:
                    if resp.status >= 400:
                        yield await resp.read()
                        return
                    async for chunk in resp.content.iter_any():
                        yield chunk

        return StreamingResponse(stream(), media_type="text/event-stream")

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, headers=headers, json=routed_body) as resp:
            try:
                content = await resp.json()
            except Exception:
                content = {"error": {"message": await resp.text(), "type": "upstream_error"}}
            if isinstance(content, dict):
                content["sources"] = sources
            return JSONResponse(status_code=resp.status, content=content)
