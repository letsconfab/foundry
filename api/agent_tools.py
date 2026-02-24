from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from models import Confab
import logging

logger = logging.getLogger(__name__)


def get_purpose(db: Session, confab_id: int) -> Optional[str]:
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return None
    cfg = confab.config or {}
    # Purpose may be stored in config.conversation.system_prompt or custom_settings.purpose
    return cfg.get("conversation", {}).get("system_prompt") or cfg.get("custom_settings", {}).get("purpose")


def update_purpose(db: Session, confab_id: int, purpose_markdown: str) -> bool:
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return False
    cfg = confab.config or {}
    if "conversation" not in cfg:
        cfg["conversation"] = {}
    cfg["conversation"]["system_prompt"] = purpose_markdown
    # also mirror into custom_settings.purpose for convenience
    if "custom_settings" not in cfg:
        cfg["custom_settings"] = {}
    cfg["custom_settings"]["purpose"] = purpose_markdown
    confab.config = cfg
    db.commit()
    return True


def search_knowledge_base(db: Session, confab_id: int, query: str) -> List[Dict[str, Any]]:
    """
    Simple DB-backed knowledge base search implemented as entries in Confab.config['knowledge_documents'].
    This is an MVP: performs case-insensitive substring matching over stored documents' content/title.
    """
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return []
    cfg = confab.config or {}
    docs = cfg.get("knowledge_documents", [])
    q = query.lower()
    results = [d for d in docs if q in (d.get("content","") + d.get("title","")).lower()]
    return results


def update_knowledge_base(db: Session, confab_id: int, file_name: str, information: str) -> bool:
    """
    Upsert a knowledge document in Confab.config['knowledge_documents'] by file_name.
    """
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return False
    cfg = confab.config or {}
    docs = cfg.get("knowledge_documents", [])
    # find existing
    for d in docs:
        if d.get("file_name") == file_name:
            d["content"] = information
            break
    else:
        docs.append({"file_name": file_name, "title": file_name, "content": information})
    cfg["knowledge_documents"] = docs
    confab.config = cfg
    db.commit()
    return True
