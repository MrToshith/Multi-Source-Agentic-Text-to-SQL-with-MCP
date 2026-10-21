"""
LLM Client for Dialect-Aware Text-to-SQL Generation.
Connects to local Ollama or OpenAI-compatible endpoints with dynamic schema context from MCP.
"""

import json
import logging
import os
import re
from typing import Any, Dict, Optional
import httpx

from src.config import config

logger = logging.getLogger("text2sql.llm")


def clean_sql(raw_response: str) -> str:
    """Strips markdown code fences, comments, and conversational chatter to isolate executable SQL."""
    text = raw_response.strip()

    # Extract content inside ```sql ... ``` or ``` ... ```
    match = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        text = match.group(1).strip()

    # Remove any conversational prefixes like "Here is the SQL query:"
    text = re.sub(r"^(?:here\s+is\s+the\s+sql(?:\s+query)?[:\s]*|sql:\s*)", "", text, flags=re.IGNORECASE).strip()

    # Remove trailing semicolons
    text = re.sub(r";+\s*$", "", text).strip()
    return text


class LLMClient:
    """Handles LLM communication for Text-to-SQL generation."""

    def __init__(
        self,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.provider = (provider or config.llm.provider).lower()
        self.base_url = (base_url or config.llm.base_url).rstrip("/")
        self.model = model or config.llm.model_name
        self.api_key = api_key or config.llm.api_key or os.getenv("OPENAI_API_KEY")
        self.timeout = timeout or config.llm.timeout_seconds

    def is_available(self) -> bool:
        """Checks if the configured LLM endpoint is reachable."""
        # If OpenAI API key is configured
        if self.provider == "openai" or (self.api_key and "openai" in self.base_url.lower()):
            return bool(self.api_key)

        # Check local Ollama endpoint
        try:
            with httpx.Client(timeout=1.0) as client:
                r = client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    def generate_sql(
        self,
        prompt: str,
        system_prompt: str,
    ) -> Optional[str]:
        """Calls the configured LLM provider and returns the cleaned SQL query."""
        if not self.is_available():
            return None

        try:
            # 1. OpenAI or OpenAI-compatible format
            if self.provider == "openai" or self.api_key:
                headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                url = f"{self.base_url}/v1/chat/completions" if "v1" not in self.base_url else f"{self.base_url}/chat/completions"
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": config.llm.temperature,
                }
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return clean_sql(content)

            # 2. Local Ollama API format
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {"temperature": config.llm.temperature},
            }
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                raw_text = resp.json().get("response", "")
                return clean_sql(raw_text)

        except Exception as e:
            logger.warning("LLM SQL generation call failed: %s", e)
            return None

    def generate_text(
        self,
        prompt: str,
        system_prompt: str = "",
    ) -> Optional[str]:
        """Calls LLM for general natural language explanation/synthesis."""
        if not self.is_available():
            return None

        try:
            if self.provider == "openai" or self.api_key:
                headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                url = f"{self.base_url}/v1/chat/completions" if "v1" not in self.base_url else f"{self.base_url}/chat/completions"
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": config.llm.temperature,
                }
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    return resp.json()["choices"][0]["message"]["content"].strip()

            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {"temperature": config.llm.temperature},
            }
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                return resp.json().get("response", "").strip()
        except Exception as e:
            logger.warning("LLM text generation call failed: %s", e)
            return None


default_llm_client = LLMClient()
