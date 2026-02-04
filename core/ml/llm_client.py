from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import urllib.request


@dataclass
class LlmResponse:
    text: str
    confidence: float
    used_llm: bool


class LlmClient:
    """
    Thin wrapper around an LLM endpoint.
    Defaults to Ollama-compatible API if configured.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ) -> None:
        self.base_url = base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1")

    def summarize_rca(self, question: str, evidence: str) -> LlmResponse:
        prompt = (
            "You are an RCA assistant. "
            "Given the evidence logs, identify the likely root cause "
            "and provide a concise explanation and suggestion.\n\n"
            f"Question: {question}\n\n"
            f"Evidence:\n{evidence}\n\n"
            "Return a 4-6 sentence summary."
        )

        try:
            payload = json.dumps({
                "model": self.model,
                "prompt": prompt,
                "stream": False,
            }).encode("utf-8")

            req = urllib.request.Request(
                url=f"{self.base_url}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data.get("response", "").strip()

            if not text:
                raise RuntimeError("Empty LLM response")

            return LlmResponse(text=text, confidence=0.7, used_llm=True)
        except Exception:
            return LlmResponse(
                text="LLM not available; generated an extractive summary instead.",
                confidence=0.35,
                used_llm=False,
            )
