"""
Foreman V3 Message Adapters

Bridges between V2's Message ORM objects and LangGraph's message types.
This adapter layer allows reuse of V2's extraction functions which expect
specific context string formats.
"""

from typing import List, TYPE_CHECKING

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

if TYPE_CHECKING:
    from models import Message


def orm_to_langgraph(messages: List["Message"]) -> List[BaseMessage]:
    """
    Convert V2 Message ORM objects to LangGraph message types.

    Args:
        messages: List of Message ORM objects with .role and .content

    Returns:
        List of LangGraph HumanMessage/AIMessage objects
    """
    result: List[BaseMessage] = []
    for msg in messages:
        if msg.role == "user":
            result.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            result.append(AIMessage(content=msg.content))
        # Skip system messages or unknown roles
    return result


def langgraph_to_context(messages: List[BaseMessage], exclude_last: bool = True) -> str:
    """
    Build V2-style context string from LangGraph messages.

    This creates the conversation context format expected by V2's
    extraction functions (e.g., extract_purpose).

    Args:
        messages: List of LangGraph message objects
        exclude_last: If True, exclude the last message (current user input)

    Returns:
        Formatted context string like:
        "User: message 1
        Foreman: response 1
        User: message 2"
    """
    if not messages:
        return ""

    msgs_to_process = messages[:-1] if exclude_last else messages

    lines = []
    for msg in msgs_to_process:
        if isinstance(msg, HumanMessage):
            lines.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            lines.append(f"Foreman: {msg.content}")
    return "\n".join(lines)


def langgraph_to_orm_style(messages: List[BaseMessage]) -> List[dict]:
    """
    Convert LangGraph messages to ORM-style dictionaries.

    Useful for compatibility with V2 code that expects message dicts.

    Args:
        messages: List of LangGraph message objects

    Returns:
        List of dicts with 'role' and 'content' keys
    """
    result = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "assistant", "content": msg.content})
    return result


def get_last_user_message(messages: List[BaseMessage]) -> str:
    """
    Extract the content of the last user message.

    Args:
        messages: List of LangGraph message objects

    Returns:
        Content of the last HumanMessage, or empty string if none found
    """
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""
