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


# ---------- setup step utilities (tools) ---------

def mark_step_complete(db: Session, confab_id: int, step: int) -> bool:
    """Record that the given configuration step has been finished on the confab."""
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return False
    cfg = confab.config or {}
    completed = cfg.get("setup_steps_completed", [])
    if step not in completed:
        completed.append(step)
    cfg["setup_steps_completed"] = completed
    confab.config = cfg
    db.commit()
    return True


def define_purpose(db: Session, confab_id: int, purpose_text: str) -> str:
    """Tool: save purpose and mark step 1."""
    update_purpose(db, confab_id, purpose_text)
    mark_step_complete(db, confab_id, 1)
    return "Purpose defined successfully."


def add_participant(db: Session, confab_id: int, email: str) -> str:
    """Tool: add a participant email (step 2)."""
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return "Confab not found."
    cfg = confab.config or {}
    parts = cfg.get("participants", [])
    if email not in parts:
        parts.append(email)
    cfg["participants"] = parts
    confab.config = cfg
    db.commit()
    mark_step_complete(db, confab_id, 2)
    return "Participant added."


def configure_memory(db: Session, confab_id: int, memory_notes: str, enable: bool = True) -> str:
    """Tool: configure memory settings (step 3)."""
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return "Confab not found."
    cfg = confab.config or {}
    if "conversation" not in cfg:
        cfg["conversation"] = {}
    cfg["conversation"]["memory_enabled"] = enable
    if "custom_settings" not in cfg:
        cfg["custom_settings"] = {}
    cfg["custom_settings"]["memory_notes"] = memory_notes
    confab.config = cfg
    db.commit()
    mark_step_complete(db, confab_id, 3)
    return "Memory configuration updated."


def add_tools_and_apis(db: Session, confab_id: int, tool_name: str, api_key: str) -> str:
    """Tool: register external tool/api (step 4)."""
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return "Confab not found."
    cfg = confab.config or {}
    integrations = cfg.get("integrations", {}).get("apis", [])
    integrations.append({"name": tool_name, "key": api_key})
    if "integrations" not in cfg:
        cfg["integrations"] = {}
    cfg["integrations"]["apis"] = integrations
    confab.config = cfg
    db.commit()
    mark_step_complete(db, confab_id, 4)
    return "Tool/API added."


def guardrails(db: Session, confab_id: int, guardrails_text: str) -> str:
    """Tool: record guardrails (step 5)."""
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return "Confab not found."
    cfg = confab.config or {}
    if "custom_settings" not in cfg:
        cfg["custom_settings"] = {}
    cfg["custom_settings"]["guardrails"] = guardrails_text
    confab.config = cfg
    db.commit()
    mark_step_complete(db, confab_id, 5)
    return "Guardrails saved."


def sample_io(db: Session, confab_id: int, sample_text: str) -> str:
    """Tool: save sample inputs/outputs (step 6)."""
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return "Confab not found."
    cfg = confab.config or {}
    if "custom_settings" not in cfg:
        cfg["custom_settings"] = {}
    cfg["custom_settings"]["sample_io"] = sample_text
    confab.config = cfg
    db.commit()
    mark_step_complete(db, confab_id, 6)
    return "Sample I/O recorded."


def review_and_save(db: Session, confab_id: int) -> str:
    """Tool: final review/save action (step 7)."""
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return "Confab not found."
    confab.status = "ready"
    db.commit()
    mark_step_complete(db, confab_id, 7)
    return "Review complete; confab marked ready."
