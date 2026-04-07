"""
Foreman V3 Extractor Nodes

Each extractor node wraps a V2 extraction function from llm_service.py
and returns state updates with a StageResult-style dict.
"""

import logging
from typing import Dict, Any

from ..state import ForemanState, StageResultDict
from ..adapters import langgraph_to_context, get_last_user_message

# Import V2 extraction functions (reuse as-is)
from llm_service import (
    extract_purpose,
    extract_participants,
    extract_memory_preference,
    extract_documents_intent,
    extract_tools,
    extract_guardrails,
    extract_sample_io,
    extract_review_intent,
)

logger = logging.getLogger(__name__)


async def extract_purpose_node(state: ForemanState) -> Dict[str, Any]:
    """
    Extract purpose from user message.

    Uses conversation context for multi-turn synthesis.
    Also extracts suggested_name for the confab.
    """
    last_msg = get_last_user_message(state["messages"])
    context = langgraph_to_context(state["messages"], exclude_last=True)

    logger.info(f"[V3] extract_purpose_node: input='{last_msg[:50]}...'")

    result = await extract_purpose(last_msg, context=context)

    if result.success and result.data:
        data = result.data

        if data.get("is_clear", False):
            return {
                "stage_result": {
                    "status": "complete",
                    "data": {
                        "purpose": data.get("purpose_text", last_msg),
                        "name": data.get("suggested_name"),
                    },
                    "summary": f"Purpose: {data.get('purpose_text', last_msg)[:100]}...",
                }
            }
        elif data.get("clarification_needed"):
            return {
                "stage_result": {
                    "status": "clarify",
                    "next_question": data["clarification_needed"],
                }
            }

    # Fallback: use raw message as purpose
    logger.warning("[V3] extract_purpose_node: extraction unclear, using raw message")
    return {
        "stage_result": {
            "status": "complete",
            "data": {"purpose": last_msg, "name": None},
            "summary": f"Purpose: {last_msg[:100]}...",
        }
    }


async def extract_participants_node(state: ForemanState) -> Dict[str, Any]:
    """
    Extract participant emails from user message.

    Handles skip intent and multiple emails.
    """
    last_msg = get_last_user_message(state["messages"])

    logger.info(f"[V3] extract_participants_node: input='{last_msg[:50]}...'")

    result = await extract_participants(last_msg)

    if result.success and result.data:
        data = result.data

        if data.get("wants_to_skip", False):
            return {
                "stage_result": {
                    "status": "skip",
                    "data": {"participants": []},
                }
            }

        emails = data.get("emails", [])
        if emails:
            return {
                "stage_result": {
                    "status": "complete",
                    "data": {"participants": emails},
                    "summary": f"Added {len(emails)} participant(s): {', '.join(emails[:3])}{'...' if len(emails) > 3 else ''}",
                }
            }

        if data.get("clarification_needed"):
            return {
                "stage_result": {
                    "status": "clarify",
                    "next_question": data["clarification_needed"],
                }
            }

    # No valid extraction
    return {
        "stage_result": {
            "status": "clarify",
            "next_question": "Could you provide an email address, or say 'skip' to continue?",
        }
    }


async def extract_memory_node(state: ForemanState) -> Dict[str, Any]:
    """
    Extract memory preference from user message.

    Options: yes (full), no (none), limited.
    """
    last_msg = get_last_user_message(state["messages"])

    logger.info(f"[V3] extract_memory_node: input='{last_msg[:50]}...'")

    result = await extract_memory_preference(last_msg)

    if result.success and result.data:
        data = result.data

        if data.get("wants_to_skip", False):
            return {
                "stage_result": {
                    "status": "skip",
                    "data": {"memory_type": "none"},
                }
            }

        memory_type = data.get("memory_type")
        if memory_type in ("full", "limited", "none"):
            # Normalize to V2 format: "yes", "no", "limited"
            normalized = "yes" if memory_type == "full" else ("no" if memory_type == "none" else "limited")
            return {
                "stage_result": {
                    "status": "complete",
                    "data": {"memory_type": normalized},
                    "summary": f"Memory: {normalized}",
                }
            }

        if data.get("clarification_needed"):
            return {
                "stage_result": {
                    "status": "clarify",
                    "next_question": data["clarification_needed"],
                }
            }

    return {
        "stage_result": {
            "status": "clarify",
            "next_question": "Please specify: should it remember conversations? (yes/no/limited)",
        }
    }


async def extract_tools_node(state: ForemanState) -> Dict[str, Any]:
    """
    Extract tool/API requirements from user message.
    """
    last_msg = get_last_user_message(state["messages"])

    logger.info(f"[V3] extract_tools_node: input='{last_msg[:50]}...'")

    result = await extract_tools(last_msg)

    if result.success and result.data:
        data = result.data

        if data.get("wants_to_skip", False) or data.get("no_tools_needed", False):
            return {
                "stage_result": {
                    "status": "skip" if data.get("wants_to_skip") else "complete",
                    "data": {"tools": []},
                    "summary": "No tools configured",
                }
            }

        tools = data.get("tools", [])
        if tools:
            return {
                "stage_result": {
                    "status": "complete",
                    "data": {"tools": tools},
                    "summary": f"Tools: {', '.join(tools[:5])}{'...' if len(tools) > 5 else ''}",
                }
            }

        if data.get("clarification_needed"):
            return {
                "stage_result": {
                    "status": "clarify",
                    "next_question": data["clarification_needed"],
                }
            }

    return {
        "stage_result": {
            "status": "clarify",
            "next_question": "Which tools specifically? For example: web search, calendar, database, or 'none'.",
        }
    }


async def extract_documents_node(state: ForemanState) -> Dict[str, Any]:
    """
    Extract document upload intent from user message.

    Handles:
    - Skip intent ("no documents", "skip", "none")
    - Upload confirmation ("I've uploaded X", "here are my docs")
    - Upload intent ("yes, I'll upload some files")
    """
    last_msg = get_last_user_message(state["messages"])

    logger.info(f"[V3] extract_documents_node: input='{last_msg[:50]}...'")

    result = await extract_documents_intent(last_msg)

    if result.success and result.data:
        data = result.data

        if data.get("wants_to_skip", False):
            return {
                "stage_result": {
                    "status": "skip",
                    "data": {"documents": [], "documents_skipped": True},
                    "summary": "Documents skipped",
                }
            }

        if data.get("has_uploads", False):
            # User confirms they've uploaded documents
            # The actual documents are already in the database via the API
            doc_count = data.get("document_count")
            summary = f"{doc_count} document(s) uploaded" if doc_count else "Documents uploaded"
            return {
                "stage_result": {
                    "status": "complete",
                    "data": {"documents": [], "documents_skipped": False},  # Actual docs fetched via API
                    "summary": summary,
                }
            }

        if data.get("wants_to_upload", False):
            # User wants to upload but hasn't yet - prompt them
            return {
                "stage_result": {
                    "status": "clarify",
                    "next_question": "Please upload your documents using the upload panel, then let me know when you're done.",
                    "ui_hint": "show_upload_panel",
                }
            }

        if data.get("clarification_needed"):
            return {
                "stage_result": {
                    "status": "clarify",
                    "next_question": data["clarification_needed"],
                    "ui_hint": "show_upload_panel",
                }
            }

    # Default: ask about documents
    return {
        "stage_result": {
            "status": "clarify",
            "next_question": "Would you like to upload any reference documents? You can upload PDFs, text files, or say 'skip' to continue without documents.",
            "ui_hint": "show_upload_panel",
        }
    }


async def extract_guardrails_node(state: ForemanState) -> Dict[str, Any]:
    """
    Extract safety guardrails from user message.
    """
    last_msg = get_last_user_message(state["messages"])

    logger.info(f"[V3] extract_guardrails_node: input='{last_msg[:50]}...'")

    result = await extract_guardrails(last_msg)

    if result.success and result.data:
        data = result.data

        if data.get("wants_to_skip", False):
            return {
                "stage_result": {
                    "status": "skip",
                    "data": {"guardrails": None},
                }
            }

        guardrails_text = data.get("guardrails_text")
        if guardrails_text:
            # Ensure it's a string (V2 bug fix)
            if isinstance(guardrails_text, list):
                guardrails_text = "\n".join(f"{i+1}. {rule}" for i, rule in enumerate(guardrails_text))

            return {
                "stage_result": {
                    "status": "complete",
                    "data": {"guardrails": guardrails_text},
                    "summary": f"Guardrails: {data.get('rules_count', 'some')} rule(s) defined",
                }
            }

        if data.get("clarification_needed"):
            return {
                "stage_result": {
                    "status": "clarify",
                    "next_question": data["clarification_needed"],
                }
            }

    return {
        "stage_result": {
            "status": "clarify",
            "next_question": "What's one important rule this agent should follow?",
        }
    }


async def extract_sample_io_node(state: ForemanState) -> Dict[str, Any]:
    """
    Extract sample input/output examples from user message.
    """
    last_msg = get_last_user_message(state["messages"])

    logger.info(f"[V3] extract_sample_io_node: input='{last_msg[:50]}...'")

    result = await extract_sample_io(last_msg)

    if result.success and result.data:
        data = result.data

        if data.get("wants_to_skip", False):
            return {
                "stage_result": {
                    "status": "skip",
                    "data": {"sample_io": None},
                }
            }

        sample_text = data.get("sample_text")
        if sample_text and data.get("has_input", False):
            return {
                "stage_result": {
                    "status": "complete",
                    "data": {"sample_io": sample_text},
                    "summary": "Sample interaction saved",
                }
            }

        if data.get("clarification_needed"):
            return {
                "stage_result": {
                    "status": "clarify",
                    "next_question": data["clarification_needed"],
                }
            }

    return {
        "stage_result": {
            "status": "clarify",
            "next_question": "Can you give a quick example of what a user might ask and how the agent should respond?",
        }
    }


async def extract_review_node(state: ForemanState) -> Dict[str, Any]:
    """
    Handle review stage - confirm save or request edits.
    """
    last_msg = get_last_user_message(state["messages"])

    logger.info(f"[V3] extract_review_node: input='{last_msg[:50]}...'")

    # Check for "show configuration" request
    lower_msg = last_msg.lower()
    if any(phrase in lower_msg for phrase in ["show config", "show the config", "view config", "see config"]):
        return {
            "stage_result": {
                "status": "clarify",
                "next_question": "_show_config",  # Special signal for responder
            }
        }

    result = await extract_review_intent(last_msg)

    if result.success and result.data:
        data = result.data
        intent = data.get("intent")

        if intent == "confirm":
            return {
                "stage_result": {
                    "status": "complete",
                    "data": {"confirmed": True},
                    "summary": "Configuration confirmed",
                }
            }

        if intent == "edit":
            edit_target = data.get("edit_target")
            if edit_target:
                return {
                    "stage_result": {
                        "status": "clarify",
                        "next_question": f"_edit:{edit_target}",  # Signal to route to edit
                    }
                }

        if data.get("clarification_needed"):
            return {
                "stage_result": {
                    "status": "clarify",
                    "next_question": data["clarification_needed"],
                }
            }

    return {
        "stage_result": {
            "status": "clarify",
            "next_question": "Would you like to make any changes, or shall I save this configuration?",
        }
    }
