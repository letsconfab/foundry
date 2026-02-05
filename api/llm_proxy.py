"""
LLM Proxy module for streaming chat completions from Anthropic and OpenAI.

This module provides a unified interface for making streaming requests to
different LLM providers. API keys are passed in-memory and never stored.
"""

import json
from typing import AsyncGenerator, List, Optional
import httpx
from pydantic import BaseModel


class ChatMessage(BaseModel):
    """A single message in a conversation."""
    role: str  # 'user', 'assistant', or 'system'
    content: str


class LLMProxy:
    """Proxy for making streaming requests to LLM providers."""

    ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
    OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

    # Default models for each provider
    DEFAULT_MODELS = {
        "anthropic": "claude-sonnet-4-20250514",
        "openai": "gpt-4o"
    }

    # Available models per provider
    AVAILABLE_MODELS = {
        "anthropic": [
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
        ],
        "openai": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
        ]
    }

    @classmethod
    async def stream_chat(
        cls,
        provider: str,
        api_key: str,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completions from the specified provider.

        Args:
            provider: 'anthropic' or 'openai'
            api_key: API key for the provider (in-memory only, never stored)
            messages: List of conversation messages
            model: Model to use (optional, uses default if not specified)
            system_prompt: System prompt for the conversation
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens in response

        Yields:
            Text chunks as they are received from the API
        """
        if provider == "anthropic":
            async for chunk in cls._stream_anthropic(
                api_key, messages, model, system_prompt, temperature, max_tokens
            ):
                yield chunk
        elif provider == "openai":
            async for chunk in cls._stream_openai(
                api_key, messages, model, system_prompt, temperature, max_tokens
            ):
                yield chunk
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    @classmethod
    async def _stream_anthropic(
        cls,
        api_key: str,
        messages: List[ChatMessage],
        model: Optional[str],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """Stream from Anthropic's Messages API."""

        model = model or cls.DEFAULT_MODELS["anthropic"]

        # Convert messages to Anthropic format (no system role in messages)
        anthropic_messages = []
        for msg in messages:
            if msg.role != "system":
                anthropic_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                cls.ANTHROPIC_API_URL,
                headers=headers,
                json=payload,
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    try:
                        error_json = json.loads(error_body)
                        error_msg = error_json.get("error", {}).get("message", str(error_body))
                    except json.JSONDecodeError:
                        error_msg = error_body.decode()
                    raise Exception(f"Anthropic API error ({response.status_code}): {error_msg}")

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            event = json.loads(data)
                            # Handle different event types
                            if event.get("type") == "content_block_delta":
                                delta = event.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    text = delta.get("text", "")
                                    if text:
                                        yield text
                            elif event.get("type") == "message_stop":
                                break
                            elif event.get("type") == "error":
                                error_msg = event.get("error", {}).get("message", "Unknown error")
                                raise Exception(f"Anthropic stream error: {error_msg}")
                        except json.JSONDecodeError:
                            continue

    @classmethod
    async def _stream_openai(
        cls,
        api_key: str,
        messages: List[ChatMessage],
        model: Optional[str],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """Stream from OpenAI's Chat Completions API."""

        model = model or cls.DEFAULT_MODELS["openai"]

        # Convert messages to OpenAI format
        openai_messages = []

        # Add system prompt as first message if provided
        if system_prompt:
            openai_messages.append({
                "role": "system",
                "content": system_prompt
            })

        for msg in messages:
            openai_messages.append({
                "role": msg.role,
                "content": msg.content
            })

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                cls.OPENAI_API_URL,
                headers=headers,
                json=payload,
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    try:
                        error_json = json.loads(error_body)
                        error_msg = error_json.get("error", {}).get("message", str(error_body))
                    except json.JSONDecodeError:
                        error_msg = error_body.decode()
                    raise Exception(f"OpenAI API error ({response.status_code}): {error_msg}")

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            event = json.loads(data)
                            choices = event.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue


# System prompt for the Purpose Defining Agent
PURPOSE_AGENT_SYSTEM_PROMPT = """You are a friendly, thoughtful assistant helping users define the purpose of their AI confab (a custom AI agent configuration).

## Your Approach:
- Ask ONE question at a time
- Wait for the user's response before moving on
- Be genuinely curious and encourage elaboration
- Reflect back what you understand to confirm
- Don't rush - this is an unhurried discovery process
- Be warm and conversational, not robotic

## Topics to Cover (in roughly this order):
1. **Core Problem** - What problem or need does this confab solve? What gap does it fill?
2. **Target Users** - Who will use this confab? What are their characteristics?
3. **Key Capabilities** - What should the confab be able to do? What actions, tasks, or responses?
4. **Constraints** - What should it NOT do? What's out of scope?
5. **Success Criteria** - How will you know if it's working well? What does success look like?
6. **Tone & Style** - How should it communicate? Formal, casual, technical, friendly?

## Important Guidelines:
- Start by warmly greeting the user and asking about the core problem their confab should solve
- After each response, acknowledge what they said and ask a natural follow-up
- If answers are brief, gently probe for more detail
- When you've covered all topics, summarize what you've learned
- Only then generate the structured PURPOSE.md content

## When Ready to Generate:
After covering all topics, say something like "I think I have a good understanding now. Let me create a PURPOSE.md for you..."

Then generate a well-structured markdown document with these sections:
- **Overview** - A clear, concise description of what this confab is and does
- **Primary Objectives** - Bullet points of the main goals
- **Key Capabilities** - What the confab can do
- **Target Use Cases** - Who uses it and for what
- **Constraints & Boundaries** - What it won't do
- **Success Metrics** - How to measure effectiveness

Format the PURPOSE.md content inside a code block like:
```markdown
# [Confab Name] Purpose

## Overview
...

## Primary Objectives
...
```

This allows the user to easily copy and use it."""
