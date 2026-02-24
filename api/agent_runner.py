from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from models import Confab
from ollama_service import ask_ollama
import logging

logger = logging.getLogger(__name__)


async def run_stage(db: Session, confab_id: int, stage_id: str, user_input: str, temperature: float = 0.7) -> Dict[str, Any]:
    """
    Minimal AgentRunner: finds stage in confab.config by id or index (string/int), renders prompt, calls Ollama,
    saves the result into confab.config.stages[].result and returns structured output.
    This is an MVP and intentionally simple — later we can add tool execution via agent_tools and LangChain.
    """
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        raise ValueError("Confab not found")

    cfg = confab.config or {}
    stages = cfg.get("stages", [])

    # Identify stage: allow numeric index or string id matching
    stage = None
    stage_idx = None
    try:
        idx = int(stage_id)
        if 0 <= idx - 1 < len(stages):
            stage_idx = idx - 1
            stage = stages[stage_idx]
    except Exception:
        # fallback: find by name or id
        for i, s in enumerate(stages):
            if str(s.get("id")) == str(stage_id) or s.get("name") == stage_id:
                stage_idx = i
                stage = s
                break

    if stage is None:
        raise ValueError("Stage not found in confab config")

    prompt_template = stage.get("prompt_template") or "{input}"
    # Simple templating: replace {input} placeholder
    prompt = prompt_template.replace("{input}", user_input)

    # Optionally include confab system prompt
    system_prompt = cfg.get("conversation", {}).get("system_prompt")
    if system_prompt:
        prompt = system_prompt + "\n\n" + prompt

    # Call Ollama
    try:
        response_text = await ask_ollama(prompt=prompt, temperature=temperature)
    except Exception as e:
        logger.error(f"AgentRunner: Ollama call failed: {e}")
        raise

    # Save result into confab.config
    result_obj = {
        "output": response_text,
        "input": user_input,
    }
    stages[stage_idx]["result"] = result_obj
    cfg["stages"] = stages
    confab.config = cfg
    db.commit()

    return {"stage": stage.get("name"), "stage_id": stage.get("id") or stage_idx + 1, "result": result_obj}
