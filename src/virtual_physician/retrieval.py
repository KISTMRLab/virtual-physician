from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class SourceChunk:
    source_id: str
    title: str
    url: str
    reviewed_at: str
    text: str


@dataclass(frozen=True)
class Evidence:
    source_id: str
    title: str
    url: str
    text: str
    score: float


def _tokens(text: str) -> list[str]:
    return TOKEN.findall(text.casefold())


def load_sources(path: str | Path) -> list[SourceChunk]:
    chunks: list[SourceChunk] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            chunk = SourceChunk(**json.loads(line))
            if not all((chunk.source_id.strip(), chunk.title.strip(), chunk.text.strip())):
                raise ValueError("source_id, title, and text are required")
            if urlparse(chunk.url).scheme != "https":
                raise ValueError("source URL must use HTTPS")
            date.fromisoformat(chunk.reviewed_at)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{path}:{line_number}: {exc}") from exc
        chunks.append(chunk)
    if not chunks:
        raise ValueError("source collection is empty")
    return chunks


class GroundedRetriever:
    """Small local TF-IDF retriever with source-preserving extractive answers."""

    def __init__(self, chunks: list[SourceChunk]):
        self.chunks = chunks
        self.term_counts = [Counter(_tokens(chunk.text)) for chunk in chunks]
        document_frequency = Counter({term: sum(term in counts for counts in self.term_counts) for counts in self.term_counts for term in counts})
        self.idf = {term: math.log((1 + len(chunks)) / (1 + frequency)) + 1 for term, frequency in document_frequency.items()}
        self.vectors = [self._vector(counts) for counts in self.term_counts]

    @classmethod
    def load(cls, path: str | Path) -> "GroundedRetriever":
        return cls(load_sources(path))

    def _vector(self, counts: Counter) -> dict[str, float]:
        total = sum(counts.values()) or 1
        return {term: count / total * self.idf.get(term, 0.0) for term, count in counts.items()}

    def search(self, question: str, limit: int = 3) -> list[Evidence]:
        query = self._vector(Counter(_tokens(question)))
        query_norm = math.sqrt(sum(value * value for value in query.values())) or 1.0
        ranked = []
        for chunk, vector in zip(self.chunks, self.vectors):
            norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
            score = sum(value * vector.get(term, 0.0) for term, value in query.items()) / (query_norm * norm)
            if score > 0:
                ranked.append(Evidence(chunk.source_id, chunk.title, chunk.url, chunk.text, score))
        return sorted(ranked, key=lambda item: item.score, reverse=True)[:limit]

    def answer(self, question: str, limit: int = 3) -> dict:
        evidence = self.search(question, limit)
        if not evidence:
            return {"answer": "The reviewed source collection does not contain enough matching information to answer that question. Please ask the clinical team.", "citations": [], "grounded": False}
        query_terms = set(_tokens(question))
        sentences: list[tuple[int, str, Evidence]] = []
        for item in evidence:
            for sentence in re.split(r"(?<=[.!?])\s+", item.text):
                overlap = len(query_terms.intersection(_tokens(sentence)))
                if overlap:
                    sentences.append((overlap, sentence.strip(), item))
        selected = sorted(sentences, key=lambda row: row[0], reverse=True)[:3]
        answer = " ".join(sentence for _, sentence, _ in selected) or evidence[0].text
        used_ids = {item.source_id for _, _, item in selected} or {evidence[0].source_id}
        citations = [{"source_id": item.source_id, "title": item.title, "url": item.url, "passage": item.text, "score": round(item.score, 4)} for item in evidence if item.source_id in used_ids]
        return {"answer": answer, "citations": citations, "grounded": True}

