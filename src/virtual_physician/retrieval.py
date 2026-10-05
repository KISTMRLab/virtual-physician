from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

TOKEN = re.compile(r"[^\W_]+", re.UNICODE)

# Function words carry no topical evidence. Without removing them, an
# off-topic question such as "What is the capital of France?" shares "what",
# "is", "the" and "of" with almost any passage and is reported as grounded.
STOPWORDS = frozenset(
    """
    a about above after again against all also am an and any are as at be because been before being below
    between both but by can could did do does doing down during each either else ever few for from further
    get gets got had has have having he her here hers herself him himself his how however i if in into is it
    its itself just let lets like may me might more most much must my myself no nor not now of off on once
    only or other ought our ours ourselves out over own please same shall she should so some such tell than
    that the their theirs them themselves then there these they this those through to too under until up upon
    us very was we were what when where whether which while who whom whose why will with would yes yet you
    your yours yourself yourselves
    """.split()
)

DECLINE = ("The reviewed source collection does not contain enough matching information to answer that question. "
           "Please ask the clinical team.")


def _normalize(token: str) -> str:
    """Conservative suffix folding so 'confirm', 'confirmed' and 'confirms' match."""
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _tokens(text: str) -> list[str]:
    return [_normalize(token) for token in TOKEN.findall(text.casefold()) if token not in STOPWORDS]


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
    coverage: float = 0.0


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


def split_sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


class GroundedRetriever:
    """Small local TF-IDF retriever with source-preserving extractive answers.

    A passage counts as evidence only when its cosine score reaches
    ``min_score`` and it contains at least ``min_coverage`` of the question's
    content words (stopwords removed). Questions without such evidence decline.
    """

    def __init__(self, chunks: list[SourceChunk], *, min_score: float = 0.12, min_coverage: float = 0.34):
        self.chunks = chunks
        self.min_score = float(min_score)
        self.min_coverage = float(min_coverage)
        self.term_counts = [Counter(_tokens(chunk.text)) for chunk in chunks]
        document_frequency = Counter(term for counts in self.term_counts for term in counts)
        self.idf = {term: math.log((1 + len(chunks)) / (1 + frequency)) + 1 for term, frequency in document_frequency.items()}
        self.vectors = [self._vector(counts) for counts in self.term_counts]

    @classmethod
    def load(cls, path: str | Path, **kwargs) -> "GroundedRetriever":
        return cls(load_sources(path), **kwargs)

    def _vector(self, counts: Counter) -> dict[str, float]:
        total = sum(counts.values()) or 1
        return {term: count / total * self.idf.get(term, 0.0) for term, count in counts.items()}

    def rank(self, question: str) -> list[Evidence]:
        """All passages with any content-word overlap, best first, before the grounding floor."""
        terms = Counter(_tokens(question))
        query = self._vector(terms)
        query_norm = math.sqrt(sum(value * value for value in query.values())) or 1.0
        ranked = []
        for chunk, counts, vector in zip(self.chunks, self.term_counts, self.vectors):
            norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
            score = sum(value * vector.get(term, 0.0) for term, value in query.items()) / (query_norm * norm)
            if score > 0:
                coverage = sum(1 for term in terms if term in counts) / max(1, len(terms))
                ranked.append(Evidence(chunk.source_id, chunk.title, chunk.url, chunk.text, score, coverage))
        return sorted(ranked, key=lambda item: item.score, reverse=True)

    def search(self, question: str, limit: int = 3) -> list[Evidence]:
        """Passages that clear the score and content-coverage floors."""
        return [item for item in self.rank(question) if item.score >= self.min_score and item.coverage >= self.min_coverage][:limit]

    def answer(self, question: str, limit: int = 3) -> dict:
        evidence = self.search(question, limit)
        if not evidence:
            return {"answer": DECLINE, "citations": [], "grounded": False}
        query_terms = set(_tokens(question))
        sentences: list[tuple[int, str, Evidence]] = []
        for item in evidence:
            for sentence in split_sentences(item.text):
                overlap = len(query_terms.intersection(_tokens(sentence)))
                if overlap:
                    sentences.append((overlap, sentence, item))
        selected = sorted(sentences, key=lambda row: row[0], reverse=True)[:3]
        answer = " ".join(sentence for _, sentence, _ in selected) or evidence[0].text
        used_ids = {item.source_id for _, _, item in selected} or {evidence[0].source_id}
        citations = [citation(item) for item in evidence if item.source_id in used_ids]
        return {"answer": answer, "citations": citations, "grounded": True}


def citation(item: Evidence) -> dict:
    return {"source_id": item.source_id, "title": item.title, "url": item.url, "passage": item.text, "score": round(item.score, 4)}
