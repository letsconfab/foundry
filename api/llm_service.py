"""
LLM Service Module - Groq API Integration
Handles all interactions with Groq API for generating chat responses.
"""

import os
import aiohttp
import logging
from typing import Optional

logger = logging.getLogger(__name__)

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

async def ask_llm(prompt: str, temperature: float = 0.7) -> str:
    """Convenience function to ask the LLM a question using LangChain with bound tools."""
    try:
        from agent_runner import get_llm
        
        # Get the LLM instance with tools bound
        llm = get_llm()
        
        # Create a message format for the LLM
        from langchain_core.messages import HumanMessage
        
        messages = [HumanMessage(content=prompt)]
        
        # Invoke the LLM - it will have access to bound tools
        response = llm.invoke(messages)
        
        return response.content
        
    except Exception as e:
        logger.error(f"Error using LangChain LLM: {e}")
        # Fallback to direct HTTP call if LangChain fails
        return await llm_client.generate_response(prompt, temperature)
