import json

from virtual_physician.behavior import section_payload
from virtual_physician.content import ScriptSection
from virtual_physician.forms import QuestionnaireFlow
from virtual_physician.retrieval import GroundedRetriever, SourceChunk, load_sources


def test_retrieval_answer_preserves_public_source_provenance(tmp_path):
    path = tmp_path / "sources.jsonl"
    path.write_text(json.dumps({"source_id": "reviewed-1", "title": "Reviewed source", "url": "https://example.org/source", "reviewed_at": "2026-01-02", "text": "The reviewed preparation passage discusses fasting instructions."}) + "\n", encoding="utf-8")
    retriever = GroundedRetriever(load_sources(path))
    response = retriever.answer("What are the fasting instructions?")
    assert response["grounded"] and response["citations"][0]["url"] == "https://example.org/source"


def test_section_emits_face_gesture_speech_and_visemes():
    payload = section_payload(ScriptSection("intro", "Clinician reviewed explanation.", "neutral", 1, "reassure"))
    assert {event["channel"] for event in payload["events"]} == {"speech", "expression", "gesture", "viseme"}


def test_questionnaire_branches_without_scoring():
    flow = QuestionnaireFlow("Feedback", "clear", (
        {"id": "clear", "type": "number", "prompt": "Was this clear?", "branches": [{"operator": "lte", "value": 2, "target": "comment"}], "next": "done"},
        {"id": "comment", "type": "text", "prompt": "What should be clearer?", "next": "done"},
        {"id": "done", "type": "message", "prompt": "Thank you", "next": None},
    ))
    flow.validate()
    assert flow.next_id("clear", "1") == "comment"
    assert flow.next_id("clear", "5") == "done"

