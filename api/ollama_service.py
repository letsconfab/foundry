"""
[CLAUDE: Ollama Service Module]
This module handles all interactions with the Ollama API for generating dynamic chat responses.
Ollama runs locally at http://localhost:11434 and provides LLM capabilities.

Configuration:
- OLLAMA_BASE_URL: http://localhost:11434
- OLLAMA_API_KEY: ollama
- OLLAMA_MODEL_NAME: gemma3:4b
"""

import os
import aiohttp
import logging
from typing import Optional
from schemas import OllamaRequest, OllamaResponse

logger = logging.getLogger(__name__)

# Load Ollama configuration from environment
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")
OLLAMA_MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "gemma3:4b")

class OllamaClient:
    """
    Client for interacting with Ollama API.
    Provides methods for generating text responses using local LLM models.
    """

    def __init__(self, base_url: str = OLLAMA_BASE_URL, api_key: str = OLLAMA_API_KEY, model: str = OLLAMA_MODEL_NAME):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout = aiohttp.ClientTimeout(total=300)  # 5 minute timeout for long responses

    async def generate_response(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> str:
        """
        Generate a response from Ollama using the specified prompt.

        Args:
            prompt: The user prompt to send to the model
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens in response (optional)
            stream: Whether to stream the response

        Returns:
            Generated response text from the model

        Raises:
            Exception: If Ollama API call fails
        """
        try:
            logger.info(f"Generating response with Ollama model: {self.model}")
            
            # [CLAUDE: Format request for Ollama API]
            request_data = OllamaRequest(
                model=self.model,
                prompt=prompt,
                stream=stream,
                temperature=temperature
            )

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Use Ollama's generate endpoint
                endpoint = f"{self.base_url}/api/generate"
                
                async with session.post(
                    endpoint,
                    json=request_data.model_dump(),
                    headers={"Content-Type": "application/json"}
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Ollama API error (status {resp.status}): {error_text}")
                        raise Exception(f"Ollama API error: {resp.status} - {error_text}")

                    # [CLAUDE: Parse Ollama response]
                    result = await resp.json()
                    logger.info("Successfully generated response from Ollama")
                    
                    # Ollama returns response in 'response' field
                    return result.get("response", "")

        except aiohttp.ClientConnectorError as e:
            logger.error(f"Failed to connect to Ollama at {self.base_url}: {e}")
            raise Exception(f"Cannot connect to Ollama. Ensure it's running at {self.base_url}")
        except Exception as e:
            logger.error(f"Error generating response from Ollama: {e}")
            raise

    async def health_check(self) -> bool:
        """
        Check if Ollama service is running and accessible.

        Returns:
            True if Ollama is accessible, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    async def list_models(self) -> dict:
        """
        Get list of available models in Ollama.

        Returns:
            Dictionary with available models
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags") as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        raise Exception(f"Failed to list models: {resp.status}")
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            raise


# [CLAUDE: Create global Ollama client instance]
ollama_client = OllamaClient(
    base_url=OLLAMA_BASE_URL,
    api_key=OLLAMA_API_KEY,
    model=OLLAMA_MODEL_NAME
)


async def ask_ollama(prompt: str, temperature: float = 0.7) -> str:
    """
    Convenience function to ask Ollama a question.
    
    Args:
        prompt: The question/prompt to ask
        temperature: Sampling temperature
    
    Returns:
        The response from Ollama
    """
    return await ollama_client.generate_response(prompt, temperature=temperature)
