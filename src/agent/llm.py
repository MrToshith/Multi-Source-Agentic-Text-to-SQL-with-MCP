"""
Local LLM client wrapper (Ollama) with deterministic analytical fallback.
Ensures seamless execution whether an Ollama server is running locally or in offline CI/pytest environments.
"""

import json
import os
import socket
from typing import Any, Dict, Optional
import httpx

from src.config import config


def is_ollama_available() -> bool:
    """Checks if local Ollama server is reachable and explicitly enabled."""
    if os.getenv("USE_LIVE_LLM", "0") != "1":
        return False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.3)
    try:
        return sock.connect_ex(("localhost", 11434)) == 0
    except OSError:
        return False
    finally:
        sock.close()


class LocalLLMClient:
    """Wrapper for local Ollama inference with JSON response parsing."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or config.llm.base_url).rstrip("/")
        self.model = model or config.llm.model_name

    def generate_json(self, prompt: str, system_prompt: str = "") -> Optional[Dict[str, Any]]:
        """Attempts to call local Ollama in JSON mode; returns None if offline or disabled."""
        if not is_ollama_available():
            return None

        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": config.llm.temperature},
            }
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                raw = resp.json().get("response", "{}")
                return json.loads(raw)
        except Exception:
            return None


default_llm_client = LocalLLMClient()
