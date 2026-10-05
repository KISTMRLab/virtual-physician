"""Retrieval-augmented answer generation with pluggable LLM clients.

The paper answers patient questions with Llama 2 7B inside a RAG framework.
This module keeps that architecture without bundling a model: a client sends
the retrieved, numbered passages and the question to an OpenAI-compatible
chat endpoint (for example a local llama.cpp, vLLM or Ollama server hosting
Llama 2) or to a local command. Answers must cite the passages they use; an
unusable generation falls back to the extractive answer.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import urllib.error
import urllib.request
from typing import Protocol

from .retrieval import DECLINE, GroundedRetriever, citation

SYSTEM_PROMPT = """You are a virtual physician assistant explaining a surgical procedure to a patient.
Answer ONLY from the numbered reviewed passages supplied by the user message.
- Write two to four short sentences in plain, patient-friendly language. Explain medical terms simply.
- After every sentence, cite the passage numbers it relies on, like [1] or [1][2].
- Do not add facts, doses, risks or advice that the passages do not state.
- Do not diagnose or recommend treatment. Encourage confirming personal decisions with the clinical team.
- If the passages do not answer the question, reply exactly: INSUFFICIENT_EVIDENCE"""

INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
CITATION = re.compile(r"\[(\d{1,2})\]")


class LLMClient(Protocol):
    name: str

    def complete(self, system: str, user: str) -> str:
        """Return the model's text for one system + user message pair."""


class OpenAICompatibleClient:
    """POST /chat/completions on any OpenAI-compatible server (llama.cpp, vLLM, Ollama, hosted APIs)."""

    def __init__(self, base_url: str, model: str, api_key: str | None = None, *, timeout: float = 60.0,
                 temperature: float = 0.2, max_tokens: int = 320):
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("LLM endpoint must be an http(s) URL, e.g. http://127.0.0.1:8081/v1")
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model, self.api_key, self.timeout = model, api_key, timeout
        self.temperature, self.max_tokens = temperature, max_tokens
        self.name = f"openai-compatible:{model}"

    def complete(self, system: str, user: str) -> str:
        body = json.dumps({"model": self.model, "temperature": self.temperature, "max_tokens": self.max_tokens,
                           "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"LLM endpoint failed: {exc}") from exc
        try:
            return str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("LLM endpoint returned no chat completion") from exc


class CommandClient:
    """Run a local command; the prompt JSON {system, user} arrives on stdin and the answer is read from stdout."""

    def __init__(self, command: str | list[str], *, timeout: float = 120.0):
        self.command = shlex.split(command) if isinstance(command, str) else list(command)
        if not self.command:
            raise ValueError("LLM command is empty")
        self.timeout = timeout
        self.name = f"command:{os.path.basename(self.command[0])}"

    def complete(self, system: str, user: str) -> str:
        try:
            result = subprocess.run(self.command, input=json.dumps({"system": system, "user": user}), capture_output=True,
                                    text=True, encoding="utf-8", timeout=self.timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"LLM command failed: {exc}") from exc
        if result.returncode != 0:
            raise RuntimeError(f"LLM command exited {result.returncode}: {result.stderr.strip()[:300]}")
        return result.stdout


def client_from_settings(endpoint: str | None = None, model: str | None = None, command: str | None = None,
                         api_key: str | None = None) -> LLMClient | None:
    """Build a client from explicit settings or VP_LLM_* environment variables; None keeps extractive answers."""
    endpoint = endpoint or os.environ.get("VP_LLM_ENDPOINT")
    command = command or os.environ.get("VP_LLM_COMMAND")
    if endpoint and command:
        raise ValueError("Configure either an LLM endpoint or an LLM command, not both")
    if endpoint:
        return OpenAICompatibleClient(endpoint, model or os.environ.get("VP_LLM_MODEL", "llama-2-7b-chat"),
                                      api_key or os.environ.get("VP_LLM_API_KEY"))
    if command:
        return CommandClient(command)
    return None


def build_user_prompt(question: str, passages: list) -> str:
    numbered = "\n\n".join(f"[{index}] {item.title}\n{item.text}" for index, item in enumerate(passages, 1))
    return f"Reviewed passages:\n\n{numbered}\n\nPatient question: {question.strip()}\n\nAnswer with citations:"


def spoken_text(answer: str) -> str:
    """Remove citation markers before text-to-speech."""
    return re.sub(r"\s+([.,!?])", r"\1", CITATION.sub("", answer)).strip()


class GroundedGenerator:
    """RAG answers over the retriever's floor-filtered evidence; the extractive answer is the fallback."""

    def __init__(self, retriever: GroundedRetriever, client: LLMClient | None = None, *, limit: int = 3):
        self.retriever, self.client, self.limit = retriever, client, limit

    @property
    def mode(self) -> str:
        return "rag-generation" if self.client else "extractive-source-sentences"

    def answer(self, question: str) -> dict:
        evidence = self.retriever.search(question, self.limit)
        if not evidence:
            # Off-topic questions decline before any model call.
            return {"answer": DECLINE, "citations": [], "grounded": False, "answer_mode": "declined-no-evidence"}
        if self.client is None:
            return {**self.retriever.answer(question, self.limit), "answer_mode": "extractive-source-sentences"}
        try:
            text = self.client.complete(SYSTEM_PROMPT, build_user_prompt(question, evidence)).strip()
        except (RuntimeError, ValueError) as exc:
            return self._fallback(question, f"generation unavailable: {exc}")
        if not text or INSUFFICIENT in text:
            return {"answer": DECLINE, "citations": [], "grounded": False, "answer_mode": "declined-by-generator", "generator": self.client.name}
        cited = sorted({int(number) for number in CITATION.findall(text)})
        valid = [number for number in cited if 1 <= number <= len(evidence)]
        if not valid or len(valid) != len(cited):
            return self._fallback(question, "generated answer did not cite the supplied passages")
        return {"answer": text, "citations": [citation(evidence[number - 1]) | {"marker": number} for number in valid],
                "grounded": True, "answer_mode": "rag-generation", "generator": self.client.name}

    def _fallback(self, question: str, reason: str) -> dict:
        result = self.retriever.answer(question, self.limit)
        return {**result, "answer_mode": "extractive-fallback", "generation_error": reason,
                "generator": getattr(self.client, "name", None)}
