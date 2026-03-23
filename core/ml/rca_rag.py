from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from core.ml.llm_client import LlmClient, LlmResponse


_LINE_SPLIT = re.compile(r"\r?\n")
_NOISE_PATTERNS = [
    re.compile(r"springframework\.boot\.logging", re.IGNORECASE),
    re.compile(r"logback", re.IGNORECASE),
    re.compile(r"configurationwatchlist", re.IGNORECASE),
    re.compile(r"tomcat.*starting", re.IGNORECASE),
    re.compile(r"started .* in .* seconds", re.IGNORECASE),
]

_SIGNAL_KEYWORDS = [
    "error", "exception", "failed", "failure", "timeout", "timed out",
    "refused", "unavailable", "unhealthy", "stacktrace", "caused by",
    "connection", "rejected", "500", "503", "504", "4xx", "5xx"
]

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_TRAIN_TICKET_SERVICE_LOG = re.compile(r"train-ticket-ts-.*-service-.*\.log$", re.IGNORECASE)


@dataclass
class RcaResult:
    summary: str
    confidence: float
    references: List[str]
    llm_used: bool


class RcaRagEngine:
    """
    Lightweight RAG engine for RCA.
    - Indexes log files with TF-IDF
    - Retrieves top-k snippets
    - Uses LLM (if available) for summarization
    """

    def __init__(self, llm_client: Optional[LlmClient] = None) -> None:
        self._llm_client = llm_client
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._docs: List[str] = []
        self._doc_refs: List[str] = []
        self._matrix = None

    def build_index(self, log_path: Path) -> None:
        if not log_path.exists():
            raise FileNotFoundError(f"Log path not found: {log_path}")

        docs: List[str] = []
        refs: List[str] = []

        if log_path.is_dir():
            files = [f for f in log_path.rglob("*") if f.is_file()]
            # Prefer Train-Ticket service logs when available
            preferred = [f for f in files if _TRAIN_TICKET_SERVICE_LOG.search(f.name)]
            if preferred:
                files = preferred

            for file in files:
                content = file.read_text(encoding="utf-8", errors="ignore")
                content = _clean_text(content)
                for chunk in _chunk_text(content, max_lines=40):
                    docs.append(chunk)
                    refs.append(str(file))
        else:
            content = log_path.read_text(encoding="utf-8", errors="ignore")
            content = _clean_text(content)
            for chunk in _chunk_text(content, max_lines=40):
                docs.append(chunk)
                refs.append(str(log_path))

        if not docs:
            raise ValueError("No log content found to index.")

        vectorizer = TfidfVectorizer(
            max_features=15000,
            ngram_range=(1, 2),
            stop_words="english",
        )
        try:
            matrix = vectorizer.fit_transform(docs)
        except ValueError:
            # Fallback if stop words wipe out vocabulary in logs
            vectorizer = TfidfVectorizer(
                max_features=15000,
                ngram_range=(1, 2),
                stop_words=None,
            )
            try:
                matrix = vectorizer.fit_transform(docs)
            except ValueError:
                # Final fallback: keep docs for extractive summary without TF-IDF
                self._vectorizer = None
                self._docs = docs
                self._doc_refs = refs
                self._matrix = None
                return

        self._vectorizer = vectorizer
        self._docs = docs
        self._doc_refs = refs
        self._matrix = matrix

    def query(self, question: str, top_k: int = 5) -> Tuple[List[str], List[str]]:
        if not self._vectorizer or self._matrix is None:
            # Fallback: return first chunks if vectorizer unavailable
            snippets = self._docs[:top_k]
            refs = self._doc_refs[:top_k]
            return snippets, refs

        query_vec = self._vectorizer.transform([question])
        scores = (self._matrix @ query_vec.T).toarray().ravel()

        if scores.size == 0:
            return [], []

        top_idx = np.argsort(scores)[::-1][:top_k]
        snippets = [self._docs[i] for i in top_idx]
        refs = [self._doc_refs[i] for i in top_idx]
        return snippets, refs

    def analyse(self, question: str, top_k: int = 5) -> RcaResult:
        snippets, refs = self.query(question, top_k=top_k)
        joined = "\n\n".join(snippets)

        if self._llm_client:
            response: LlmResponse = self._llm_client.summarize_rca(
                question=question,
                evidence=joined,
            )
            if response.used_llm:
                return RcaResult(
                    summary=response.text,
                    confidence=response.confidence,
                    references=refs,
                    llm_used=True,
                )

        # Fallback: extractive summary from top snippets
        summary = _extractive_summary(snippets, refs)
        return RcaResult(
            summary=summary,
            confidence=0.35,
            references=refs,
            llm_used=False,
        )


def _chunk_text(text: str, max_lines: int = 40) -> List[str]:
    lines = [line for line in _LINE_SPLIT.split(text) if line.strip()]
    chunks = []
    for i in range(0, len(lines), max_lines):
        chunk = "\n".join(lines[i : i + max_lines])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def _clean_text(text: str) -> str:
    if not text:
        return ""
    # Drop nulls + control chars while preserving tabs/newlines for chunking.
    text = text.replace("\x00", "")
    return _CONTROL_CHARS.sub("", text)


def _extractive_summary(snippets: List[str], refs: List[str]) -> str:
    if not snippets:
        return "No RCA evidence found in logs."

    # Prefer high-signal lines and avoid startup noise
    scored_lines: List[tuple[int, str, str]] = []
    keyword_counts = {k: 0 for k in ["error", "exception", "timeout", "failed", "refused"]}
    service_hits = {}

    for snippet, ref in zip(snippets, refs or []):
        service = Path(ref).stem if ref else "unknown"
        service_hits[service] = service_hits.get(service, 0) + 1
        lines = [line.strip() for line in _LINE_SPLIT.split(snippet) if line.strip()]
        for line in lines:
            lower = line.lower()
            if any(p.search(line) for p in _NOISE_PATTERNS):
                continue
            score = 0
            for kw in _SIGNAL_KEYWORDS:
                if kw in lower:
                    score += 1
            for kw in keyword_counts:
                if kw in lower:
                    keyword_counts[kw] += 1
            if "error" in lower or "exception" in lower:
                score += 2
            scored_lines.append((score, line, service))

    # Sort by score and keep top lines; fallback to any non-noise lines
    scored_lines.sort(key=lambda x: x[0], reverse=True)
    selected = [(line, service) for score, line, service in scored_lines if score > 0][:4]

    if not selected:
        fallback = []
        for snippet, ref in zip(snippets, refs or []):
            service = Path(ref).stem if ref else "unknown"
            lines = [line.strip() for line in _LINE_SPLIT.split(snippet) if line.strip()]
            for line in lines:
                if any(p.search(line) for p in _NOISE_PATTERNS):
                    continue
                fallback.append((line, service))
        selected = fallback[:4]

    if not selected:
        return "No RCA evidence found in logs."

    # Make it developer-friendly and concise
    bullets = []
    for line, service in selected[:4]:
        cleaned = re.sub(r"\s+", " ", line).strip()
        if len(cleaned) > 200:
            cleaned = cleaned[:200] + "..."
        bullets.append(f"- [{service}] {cleaned}")

    top_service = max(service_hits, key=service_hits.get) if service_hits else "unknown"
    top_keywords = ", ".join([f"{k}={v}" for k, v in keyword_counts.items() if v > 0]) or "none"
    likely_cause = re.sub(r"\s+", " ", selected[0][0]).strip()
    if len(likely_cause) > 180:
        likely_cause = likely_cause[:180] + "..."

    return (
        f"Primary log source: {top_service}\n"
        f"Top error signals: {top_keywords}\n"
        f"Likely Cause: {likely_cause}\n"
        f"Details:\n" + "\n".join(bullets)
    )
