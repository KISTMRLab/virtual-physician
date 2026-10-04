from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .behavior import plan_behavior, section_payload
from .content import ExplanationScript
from .forms import QuestionnaireFlow
from .retrieval import GroundedRetriever


class Question(BaseModel):
    question: str


class FormAnswer(BaseModel):
    item_id: str
    answer: str


def create_app(source_path: str, script_path: str, questionnaire_path: str | None = None, static_path: str | None = None) -> FastAPI:
    retriever = GroundedRetriever.load(source_path)
    script = ExplanationScript.load(script_path)
    questionnaire = QuestionnaireFlow.load(questionnaire_path) if questionnaire_path else None
    static = Path(static_path) if static_path else Path(__file__).parents[2] / "static"
    app = FastAPI(title="Virtual physician research reimplementation")
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/")
    def index():
        return FileResponse(static / "index.html")

    @app.get("/api/script")
    def get_script():
        return {"title": script.title, "reviewed_by": script.reviewed_by, "reviewed_at": script.reviewed_at, "sections": [section_payload(section) for section in script.sections]}

    @app.post("/api/ask")
    def ask(payload: Question):
        if not payload.question.strip():
            raise HTTPException(400, "question is required")
        response = retriever.answer(payload.question)
        response["events"] = plan_behavior(response["answer"], "neutral", 1, "open_hand")
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
    args = parser.parse_args()
    app = create_app(args.sources, args.script, args.questionnaire)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

