import json

from virtual_physician.behavior import section_payload
from virtual_physician.content import ScriptSection
from virtual_physician.forms import QuestionnaireFlow
from virtual_physician.retrieval import GroundedRetriever, SourceChunk, load_sources
from virtual_physician.importer import import_source


def test_retrieval_answer_preserves_public_source_provenance(tmp_path):
    path = tmp_path / "sources.jsonl"
    path.write_text(json.dumps({"source_id": "reviewed-1", "title": "Reviewed source", "url": "https://example.org/source", "reviewed_at": "2026-01-02", "text": "The reviewed preparation passage discusses fasting instructions."}) + "\n", encoding="utf-8")
    retriever = GroundedRetriever(load_sources(path))
    response = retriever.answer("What are the fasting instructions?")
    assert response["grounded"] and response["citations"][0]["url"] == "https://example.org/source"


def test_selected_public_page_import_preserves_review_date_and_source(tmp_path):
    page = tmp_path / "page.html"
    page.write_text("<html><nav>Skip menu</nav><main><p>First educational passage provides the background.</p><p>Second passage provides relevant context for questions.</p></main></html>", encoding="utf-8")
    corpus = tmp_path / "sources.jsonl"
    import_source("https://example.org/education", "Public educational page", "page-1", "2026-10-05", corpus, page)
    source = load_sources(corpus)[0]
    assert (source.source_id, source.url, source.reviewed_at) == ("page-1", "https://example.org/education", "2026-10-05")
    assert "First educational passage" in source.text and "Second passage" in source.text
    assert "Skip menu" not in source.text


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
