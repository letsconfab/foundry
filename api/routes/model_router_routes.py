"""OpenAI-compatible model router for deployed Hermes profiles."""

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from database import get_db
from services.model_router_proxy import authorize_router, list_running_models, proxy_chat_completion

router = APIRouter(tags=["model-router"])


@router.get("/router/health")
async def router_health():
    return {"ok": True}


@router.get("/router/v1/models")
async def router_models(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    authorize_router(authorization)
    return list_running_models(db)


@router.post("/router/v1/chat/completions")
async def router_chat_completions(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    authorize_router(authorization)
    body = await request.json()
    return await proxy_chat_completion(db, body)
