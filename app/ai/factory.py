"""
Factory for LLM provider objects.

Currently only Ollama is supported.  The factory reads the configuration keys defined in ``config.json``:

- ``ollama_host`` (or legacy ``ollama_url``)
- ``ollama_model`` (or legacy ``llm_model``)
- ``provider`` – must be ``"ollama"`` for now.

The returned provider implements ``generate_response(prompt, context, system=None, on_token=None)``.  It streams tokens to the supplied callback and returns the full text.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any, Dict, List, Optional

import httpx

# Import the prompt builder used by the core
try:
    from app.core.prompts import build_system_prompt
except Exception:
    try:
        from app.prompts import build_system_prompt
    except Exception as exc:  # pragma: no cover - import error
        raise RuntimeError(f"Failed to import prompts module: {exc}")

class OllamaProvider:
    def __init__(self, host: str, model: str):
        self.host = host.rstrip("/")
        self.model = model

    async def generate_response(
        self,
        prompt: str,
        context: List[str],
        *,
        system: Optional[str] = None,
        on_token=None,
    ) -> str:
        """
        Generate a response from Ollama.

        :param prompt: User question text.
        :param context: Retrieved evidence chunks (list of strings).
        :param system: Full system prompt string; if None, a minimal prompt will be used.
        :param on_token: Optional async callback accepting each token chunk.
        :return: The full response text.
        """
        # Build messages
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        else:
            # Minimal fallback if system is not provided
            messages.append(
                {
                    "role": "system",
                    "content": "You are a helpful assistant.",
                }
            )
        messages.append({"role": "user", "content": prompt})

        full = ""
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
            async with client.stream(
                "POST",
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "stream": True,
                    "keep_alive": "30m",
                    # Pass the context via system prompt – caller is responsible for embedding it
                    "messages": messages,
                    "options": {"temperature": 0.4, "num_predict": 700},
                    "think": False,
                },
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise RuntimeError(
                        f"Ollama returned HTTP {resp.status_code}: {body.decode('utf-8', errors='ignore')}"
                    )
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if "error" in obj:
                        raise RuntimeError(f"Ollama error: {obj['error']}")
                    msg = obj.get("message", {})
                    tok = msg.get("content", "")
                    if tok:
                        full += tok
                        if on_token is not None:
                            await on_token(tok)
        return full

class ProviderFactory:
    @staticmethod
    def create_provider(cfg: Dict[str, Any]) -> OllamaProvider:
        host = cfg.get("ollama_host") or cfg.get("ollama_url", "http://127.0.0.1:11434")
        model = cfg.get("ollama_model") or cfg.get("llm_model", "hf.co/nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF:Q4_K_M")
        provider = cfg.get("provider", "ollama")
        if provider != "ollama":
            raise NotImplementedError(f"Provider {provider!r} is not supported. Only 'ollama' is supported.")
        return OllamaProvider(host, model)

__all__ = ["OllamaProvider", "ProviderFactory"]
