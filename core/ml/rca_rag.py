from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from core.ml.llm_client import LlmClient, LlmResponse


_LINE_SPLIT = re.compile(r"\r?\n")


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
            for file in log_path.rglob("*"):
                if file.is_file():
                    content = file.read_text(encoding="utf-8", errors="ignore")
                    for chunk in _chunk_text(content, max_lines=40):
                        docs.append(chunk)
                        refs.append(str(file))
        else:
            content = log_path.read_text(encoding="utf-8", errors="ignore")
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
        matrix = vectorizer.fit_transform(docs)

        self._vectorizer = vectorizer
        self._docs = docs
        self._doc_refs = refs
        self._matrix = matrix

    def query(self, question: str, top_k: int = 5) -> Tuple[List[str], List[str]]:
        if not self._vectorizer or self._matrix is None:
            raise RuntimeError("RAG index not built. Call build_index() first.")

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
        summary = _extractive_summary(snippets)
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


def _extractive_summary(snippets: List[str]) -> str:
    if not snippets:
        return "No RCA evidence found in logs."

    # Heuristic: take the first 2 lines from the top 2 snippets
    selected = []
    for snippet in snippets[:2]:
        lines = [line.strip() for line in _LINE_SPLIT.split(snippet) if line.strip()]
        selected.extend(lines[:2])

    if not selected:
        return "No RCA evidence found in logs."

    return " | ".join(selected[:4])
