from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .behavior import plan_behavior, section_payload
from .content import ExplanationScript
from .forms import QuestionnaireFlow
from .generation import GroundedGenerator, LLMClient, client_from_settings, spoken_text
from .retrieval import GroundedRetriever
from .speech_backend import SpeechBackend

REPO_ROOT = Path(__file__).resolve().parents[2]
BEAT_SETUP = ("Recorded co-speech gestures need the gesture extra and a prepared local BEAT bank: "
              "pip install -e \".[gesture]\" and python scripts/prepare_beat_demo.py. Speech and answers still work.")


class Question(BaseModel):
    question: str


class FormAnswer(BaseModel):
    item_id: str
    answer: str


def _beat_runtime():
    """Import the vendored BEAT runtime lazily so the server starts without numpy/torch."""
    scripts = str(REPO_ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import beat_runtime  # noqa: PLC0415 - optional dependency boundary
    return beat_runtime


def create_app(source_path: str, script_path: str, questionnaire_path: str | None = None, static_path: str | None = None,
               llm_client: LLMClient | None = None) -> FastAPI:
    retriever = GroundedRetriever.load(source_path)
    generator = GroundedGenerator(retriever, llm_client)
    script = ExplanationScript.load(script_path)
    personas = script.resolved_personas
    questionnaire = QuestionnaireFlow.load(questionnaire_path) if questionnaire_path else None
    speech = SpeechBackend()
    static = Path(static_path) if static_path else REPO_ROOT / "static"
    app = FastAPI(title="Virtual physician research reimplementation")
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/api/beat-library")
    def beat_library():
        try:
            return _beat_runtime().library(REPO_ROOT, "multilingual")
        except ImportError as exc:
            return {"ready": False, "message": f"{BEAT_SETUP} ({exc})"}

    @app.post("/api/beat-query")
    def beat_query(payload: dict):
        try:
            runtime = _beat_runtime()
        except ImportError as exc:
            return JSONResponse({"ready": False, "error": f"{BEAT_SETUP} ({exc})"}, status_code=503)
        try:
            return runtime.query_application(REPO_ROOT, "multilingual", str(payload.get("text", "")))
        except (ValueError, FileNotFoundError) as exc:
            return JSONResponse({"ready": False, "error": str(exc)}, status_code=400)

    @app.get("/")
    def index():
        return FileResponse(static / "index.html")

    @app.get("/api/script")
    def get_script():
        return {"title": script.title, "reviewed_by": script.reviewed_by, "reviewed_at": script.reviewed_at,
                "persona": script.persona, "personas": personas, "answer_emotion": script.answer_emotion,
                "sections": [section_payload(section, script) for section in script.sections], "mode": "authored-script"}

    @app.get("/api/speech-status")
    def speech_status():
        return {**speech.status(), "answer_mode": generator.mode, "generator": getattr(llm_client, "name", None)}

    def synthesize(text: str, voice: str | None):
        try:
            return Response(speech.synthesize(text, voice), media_type="audio/wav")
        except (ValueError, ImportError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=503)

    @app.post("/api/tts")
    def tts(payload: dict):
        return synthesize(payload.get("text", ""), payload.get("voice"))

    # Persona voices: the shared Speech client posts {text} to <base>/tts, so
    # each persona uses /api/voice/<kokoro_voice> as its base path.
    @app.post("/api/voice/{voice}/tts")
    def persona_tts(voice: str, payload: dict):
        return synthesize(payload.get("text", ""), voice)

    @app.post("/api/asr")
    async def asr(request: Request):
        try:
            return speech.transcribe(await request.body())
        except (ValueError, ImportError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=503)

    @app.post("/api/voice/{voice}/asr")
    async def persona_asr(voice: str, request: Request):
        return await asr(request)

    @app.post("/api/ask")
    def ask(payload: Question):
        if not payload.question.strip():
            raise HTTPException(400, "question is required")
        response = generator.answer(payload.question)
        style = script.answer_emotion if response["grounded"] else {"emotion": "neutral", "intensity": 1}
        response["spoken_text"] = spoken_text(response["answer"])
        response["emotion"], response["intensity"] = style["emotion"], style["intensity"]
        response["events"] = plan_behavior(response["spoken_text"], style["emotion"], style["intensity"], "auto")
        response["retrieved"] = [{"source_id": e.source_id, "title": e.title, "url": e.url, "passage": e.text,
                                  "score": round(e.score, 4), "coverage": round(e.coverage, 3)} for e in retriever.rank(payload.question)[:3]]
        response["grounding"] = {"min_score": retriever.min_score, "min_coverage": retriever.min_coverage}
        return response

    @app.get("/api/questionnaire")
    def get_questionnaire():
        if questionnaire is None:
            return {"enabled": False}
        return {"enabled": True, "title": questionnaire.title, "start_id": questionnaire.start_id, "items": list(questionnaire.items), "purpose": "research feedback only; no diagnostic or validated clinical score is calculated"}

    @app.post("/api/questionnaire/respond")
    def respond(payload: FormAnswer):
        if questionnaire is None:
            raise HTTPException(404, "questionnaire is not configured")
        return {"next_id": questionnaire.next_id(payload.item_id, payload.answer)}

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve clinician-authored explanations and grounded Q&A")
    parser.add_argument("--sources", required=True)
    parser.add_argument("--script", required=True)
    parser.add_argument("--questionnaire")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--llm-endpoint", help="OpenAI-compatible base URL, e.g. http://127.0.0.1:8081/v1 (env VP_LLM_ENDPOINT)")
    parser.add_argument("--llm-model", help="model name sent to the endpoint (env VP_LLM_MODEL; default llama-2-7b-chat)")
    parser.add_argument("--llm-command", help="local command reading {system,user} JSON on stdin (env VP_LLM_COMMAND)")
    args = parser.parse_args()
    client = client_from_settings(args.llm_endpoint, args.llm_model, args.llm_command)
    app = create_app(args.sources, args.script, args.questionnaire, llm_client=client)
    print(f"Answer mode: {'RAG generation via ' + client.name if client else 'extractive (no LLM configured)'}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
