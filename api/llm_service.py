"""
LLM Service Module - Groq API Integration
Handles all interactions with Groq API for generating chat responses.

V2 additions:
- ask_llm_json(): Structured JSON extraction at low temperature
- JSON parsing with retry on malformed output
"""

import os
import json
import aiohttp
import logging
from typing import Optional, Dict, Any, TypeVar, Type
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Default temperatures
DEFAULT_TEMPERATURE = 0.7           # V1 conversational
EXTRACTION_TEMPERATURE = 0.1        # V2 structured extraction

# Load Groq configuration from environment
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME", "qwen/qwen3-32b")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

class LLMClient:
    """Client for interacting with Groq API."""

    def __init__(self, api_key: str = GROQ_API_KEY, model: str = GROQ_MODEL_NAME):
        self.api_key = api_key
        self.model = model
        self.base_url = GROQ_BASE_URL
        self.timeout = aiohttp.ClientTimeout(total=300)

    async def generate_response(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate a response from Groq using the specified prompt."""
        if not self.api_key:
            raise Exception("GROQ_API_KEY environment variable is not set")

        try:
            logger.info(f"Generating response with Groq model: {self.model}")

            request_data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            }
            if max_tokens:
                request_data["max_tokens"] = max_tokens

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=request_data,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Groq API error (status {resp.status}): {error_text}")
                        raise Exception(f"Groq returned status {resp.status}: {error_text[:200]}")

                    result = await resp.json()
                    logger.info("Successfully generated response from Groq")
                    return result["choices"][0]["message"]["content"]

        except aiohttp.ClientConnectorError as e:
            logger.error(f"Failed to connect to Groq: {e}")
            raise Exception(f"Cannot connect to Groq API: {str(e)}")
        except Exception as e:
            logger.error(f"Error generating response from Groq: {type(e).__name__}: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if Groq API is configured and accessible."""
        return bool(self.api_key)

# Global LLM client instance
llm_client = LLMClient()


async def ask_llm(prompt: str, temperature: float = DEFAULT_TEMPERATURE) -> str:
    """Convenience function to ask the LLM a question."""
    return await llm_client.generate_response(prompt, temperature=temperature)


# =========================================================================
# V2 Structured Extraction
# =========================================================================

@dataclass
class ExtractionResult:
    """Result from structured JSON extraction."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    raw_response: Optional[str] = None
    error: Optional[str] = None


def _extract_json_from_response(response: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from an LLM response that may contain surrounding text.

    Handles:
    - Pure JSON response
    - JSON wrapped in ```json ... ``` code blocks
    - JSON embedded in prose
    """
    # Try direct parse first
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        pass

    # Try to find JSON in code block
    import re
    code_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find any JSON object
    start = response.find('{')
    if start != -1:
        depth = 0
        for i, char in enumerate(response[start:], start):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(response[start:i+1])
                    except json.JSONDecodeError:
                        pass
                    break

    return None


async def ask_llm_json(
    prompt: str,
    schema_description: str = "",
    temperature: float = EXTRACTION_TEMPERATURE,
    max_retries: int = 1
) -> ExtractionResult:
    """
    Ask the LLM for a structured JSON response.

    Uses low temperature for deterministic extraction.
    Includes retry logic for malformed JSON.

    Args:
        prompt: The extraction prompt (should request JSON output)
        schema_description: Description of expected JSON schema for error messages
        temperature: LLM temperature (default 0.1 for extraction)
        max_retries: Number of retries for malformed JSON

    Returns:
        ExtractionResult with success status, parsed data, or error
    """
    logger.debug(f"[LLM JSON] Extraction request [temp={temperature}]")

    attempts = 0
    last_error = None
    last_response = None

    while attempts <= max_retries:
        attempts += 1

        try:
            # Add JSON instruction if not already present
            if "json" not in prompt.lower():
                full_prompt = f"{prompt}\n\nRespond with valid JSON only. No other text."
            else:
                full_prompt = prompt

            # If this is a retry, add repair instruction
            if attempts > 1 and last_response:
                full_prompt = f"""Your previous response was not valid JSON:
{last_response[:500]}

Please fix it and respond with valid JSON only.

Original request:
{prompt}"""

            response = await llm_client.generate_response(
                full_prompt,
                temperature=temperature
            )
            last_response = response

            # Try to parse JSON
            parsed = _extract_json_from_response(response)

            if parsed is not None:
                logger.info(f"[LLM JSON] Extraction success [attempt={attempts}]")
                return ExtractionResult(
                    success=True,
                    data=parsed,
                    raw_response=response
                )
            else:
                last_error = "Could not parse JSON from response"
                logger.warning(
                    f"[LLM JSON] Parse failed [attempt={attempts}, "
                    f"response_preview={response[:100]}...]"
                )

        except Exception as e:
            last_error = str(e)
            logger.error(f"[LLM JSON] Request failed [attempt={attempts}]: {e}")

    logger.error(
        f"[LLM JSON] Extraction failed after {attempts} attempts: {last_error}"
    )
    return ExtractionResult(
        success=False,
        raw_response=last_response,
        error=last_error
    )


# =========================================================================
# Stage-Specific Extractors
# =========================================================================

async def extract_purpose(user_message: str, context: str = "") -> ExtractionResult:
    """Extract purpose information from user message."""
    prompt = f"""Analyze this user message about an AI agent's purpose and extract structured information.

User message: "{user_message}"

{f"Additional context: {context}" if context else ""}

Extract and return JSON with these fields:
{{
    "purpose_text": "A clear, concise description of what the agent should do (1-3 sentences)",
    "suggested_name": "A short name for this agent (1-2 words, e.g., 'SupportBot', 'DataAnalyzer')",
    "is_clear": true/false (whether the purpose is clear enough to save),
    "clarification_needed": null or "A follow-up question if more detail is needed"
}}

Respond with valid JSON only."""

    return await ask_llm_json(prompt, "purpose extraction")


async def extract_participants(user_message: str) -> ExtractionResult:
    """Extract participant emails from user message."""
    prompt = f"""Analyze this user message about adding participants to an AI agent.

User message: "{user_message}"

Extract and return JSON with these fields:
{{
    "emails": ["list", "of", "emails@found.com"],
    "wants_to_skip": true/false (whether user wants to skip this step),
    "clarification_needed": null or "A question if the message is unclear"
}}

If no valid emails are found and user doesn't want to skip, set clarification_needed.

Respond with valid JSON only."""

    return await ask_llm_json(prompt, "participant extraction")


async def extract_memory_preference(user_message: str) -> ExtractionResult:
    """Extract memory configuration preference from user message."""
    prompt = f"""Analyze this user message about memory settings for an AI agent.

User message: "{user_message}"

The user is choosing whether the agent should remember past conversations.
Options are: full memory, no memory, or limited memory (recent only).

Extract and return JSON with these fields:
{{
    "enable_memory": true/false/null (null if unclear),
    "memory_type": "full" | "limited" | "none" | null,
    "notes": "Brief description of the memory setting",
    "wants_to_skip": true/false,
    "clarification_needed": null or "A question if the preference is unclear"
}}

Respond with valid JSON only."""

    return await ask_llm_json(prompt, "memory preference extraction")


async def extract_tools(user_message: str) -> ExtractionResult:
    """Extract tool/API requirements from user message."""
    prompt = f"""Analyze this user message about tools and APIs for an AI agent.

User message: "{user_message}"

The user is specifying what external tools or APIs the agent needs access to.
Common tools: web_search, database, calendar, email, slack, custom_api.

Extract and return JSON with these fields:
{{
    "tools": ["list", "of", "tool_names"],
    "no_tools_needed": true/false (if user explicitly says no tools),
    "wants_to_skip": true/false,
    "clarification_needed": null or "A question if unclear"
}}

Respond with valid JSON only."""

    return await ask_llm_json(prompt, "tools extraction")


async def extract_guardrails(user_message: str) -> ExtractionResult:
    """Extract safety guardrails from user message."""
    prompt = f"""Analyze this user message about safety guardrails for an AI agent.

User message: "{user_message}"

The user is specifying rules, restrictions, or safety boundaries for the agent.

Extract and return JSON with these fields:
{{
    "guardrails_text": "Formatted list of guardrails/rules (can include the user's text)",
    "rules_count": number of distinct rules identified,
    "wants_to_skip": true/false,
    "clarification_needed": null or "A question if more detail is needed"
}}

Respond with valid JSON only."""

    return await ask_llm_json(prompt, "guardrails extraction")


async def extract_sample_io(user_message: str) -> ExtractionResult:
    """Extract sample input/output examples from user message."""
    prompt = f"""Analyze this user message containing example interactions for an AI agent.

User message: "{user_message}"

The user is providing sample inputs and expected outputs/responses.

Extract and return JSON with these fields:
{{
    "sample_text": "Formatted sample interaction (User: ... Agent: ...)",
    "has_input": true/false (whether a user input example is present),
    "has_output": true/false (whether an agent response example is present),
    "wants_to_skip": true/false,
    "clarification_needed": null or "A question if the example is incomplete"
}}

Respond with valid JSON only."""

    return await ask_llm_json(prompt, "sample I/O extraction")


async def extract_review_intent(user_message: str) -> ExtractionResult:
    """Extract user intent during review stage."""
    prompt = f"""Analyze this user message during the final review of an AI agent configuration.

User message: "{user_message}"

The user is either confirming they're ready to save, or requesting changes.

Extract and return JSON with these fields:
{{
    "intent": "confirm" | "edit" | "unclear",
    "edit_target": null or "which section they want to edit (purpose/participants/memory/tools/guardrails/examples)",
    "clarification_needed": null or "A question to clarify their intent"
}}

Respond with valid JSON only."""

    return await ask_llm_json(prompt, "review intent extraction")
