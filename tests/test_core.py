import json
import sys
from pathlib import Path

import pytest

from virtual_physician.behavior import section_payload
from virtual_physician.content import ExplanationScript, ScriptSection
from virtual_physician.forms import QuestionnaireFlow
from virtual_physician.generation import CommandClient, GroundedGenerator, client_from_settings, spoken_text
from virtual_physician.retrieval import GroundedRetriever, SourceChunk, load_sources
from virtual_physician.importer import import_source

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class StubClient:
    name = "stub"

    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def complete(self, system, user):
        self.calls.append((system, user))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def example_retriever():
    return GroundedRetriever.load(EXAMPLES / "sources.jsonl")


def test_retrieval_answer_preserves_public_source_provenance(tmp_path):
    path = tmp_path / "sources.jsonl"
    path.write_text(json.dumps({"source_id": "reviewed-1", "title": "Reviewed source", "url": "https://example.org/source", "reviewed_at": "2026-01-02", "text": "The reviewed preparation passage discusses fasting instructions."}) + "\n", encoding="utf-8")
    retriever = GroundedRetriever(load_sources(path))
    response = retriever.answer("What are the fasting instructions?")
    assert response["grounded"] and response["citations"][0]["url"] == "https://example.org/source"


@pytest.mark.parametrize("question", [
    "What is the capital of France?",
    "Who won the football world cup in 2018?",
    "What is the the of and is?",
])
def test_off_topic_questions_decline(question):
    # Audit regression: stopword overlap used to mark these as grounded.
    retriever = example_retriever()
    assert retriever.search(question) == []
    assert retriever.answer(question)["grounded"] is False
    stub = StubClient("Paris is the capital [1].")
    result = GroundedGenerator(retriever, stub).answer(question)
    assert result["grounded"] is False and result["answer_mode"] == "declined-no-evidence"
    assert stub.calls == [], "off-topic questions must decline before any model call"


def test_on_topic_question_is_grounded_with_inflected_terms():
    result = example_retriever().answer("Where should fasting questions be confirmed?")
    assert result["grounded"] and result["citations"][0]["source_id"] == "demo-preparation"


def test_rag_generation_cites_numbered_passages():
    stub = StubClient("Please confirm fasting questions directly with your clinical team [1].")
    result = GroundedGenerator(example_retriever(), stub).answer("Who confirms questions about fasting?")
    assert result["answer_mode"] == "rag-generation" and result["grounded"]
    assert [item["source_id"] for item in result["citations"]] == ["demo-preparation"]
    system, user = stub.calls[0]
    assert "ONLY from the numbered reviewed passages" in system and "[1] Synthetic demonstration preparation note" in user
    assert spoken_text(result["answer"]) == "Please confirm fasting questions directly with your clinical team."


@pytest.mark.parametrize("reply", ["Fasting is always twelve hours.", "Confirm with the team [7].", RuntimeError("endpoint down")])
def test_uncited_or_failed_generation_falls_back_to_extractive(reply):
    result = GroundedGenerator(example_retriever(), StubClient(reply)).answer("Who confirms questions about fasting?")
    assert result["answer_mode"] == "extractive-fallback" and result["grounded"]
    assert "confirmed directly with the clinical team" in result["answer"]


def test_generator_can_decline():
    result = GroundedGenerator(example_retriever(), StubClient("INSUFFICIENT_EVIDENCE")).answer("Who confirms questions about fasting?")
    assert result["grounded"] is False and result["answer_mode"] == "declined-by-generator"


def test_local_command_client_reads_prompt_on_stdin():
    code = "import json,sys; p=json.load(sys.stdin); print('Echo: ' + p['user'].splitlines()[2] + ' [1]')"
    client = CommandClient([sys.executable, "-c", code])
    result = GroundedGenerator(example_retriever(), client).answer("Who confirms questions about fasting?")
    assert result["answer_mode"] == "rag-generation" and result["answer"].startswith("Echo: [1]")


def test_client_settings_choose_endpoint_or_command(monkeypatch):
    monkeypatch.delenv("VP_LLM_ENDPOINT", raising=False); monkeypatch.delenv("VP_LLM_COMMAND", raising=False)
    assert client_from_settings() is None
    assert client_from_settings(endpoint="http://127.0.0.1:8081/v1", model="llama-2-7b-chat").url == "http://127.0.0.1:8081/v1/chat/completions"
    with pytest.raises(ValueError):
        client_from_settings(endpoint="http://x/v1", command="llm")


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
    payload = section_payload(ScriptSection("intro", "Clinician reviewed explanation.", "fear", 3, "reassure"))
    assert {event["channel"] for event in payload["events"]} == {"speech", "expression", "gesture", "viseme"}
    expression = next(event for event in payload["events"] if event["channel"] == "expression")
    assert (expression["value"], expression["level"]) == ("fear", 3)
    gesture = next(event for event in payload["events"] if event["channel"] == "gesture")
    assert (gesture["value"], gesture["source"]) == ("reassure", "authored")


def test_section_without_gesture_uses_recorded_retrieval():
    payload = section_payload(ScriptSection("intro", "Text.", "neutral", 1))
    assert payload["gesture"] == "auto" and payload["gesture_source"] == "retrieval"


def test_script_personas_bind_avatar_voice_and_video(tmp_path):
    script = ExplanationScript.load(EXAMPLES / "script.json")
    personas = script.resolved_personas
    assert personas["doctor"]["avatar"] == "rowan" and personas["nurse"]["avatar"] == "mira"
    assert [script.persona_for(section) for section in script.sections] == ["doctor", "doctor", "nurse"]
    raw = json.loads((EXAMPLES / "script.json").read_text(encoding="utf-8"))
    raw["sections"][0]["video_url"] = "https://media.example.org/clip.mp4"
    path = tmp_path / "script.json"; path.write_text(json.dumps(raw), encoding="utf-8")
    payload = section_payload(ExplanationScript.load(path).sections[0], script)
    assert payload["video_url"] == "https://media.example.org/clip.mp4" and payload["persona"] == "doctor"
    for bad in ({"video_url": "http://insecure.example/clip.mp4"}, {"persona": "surgeon-bot"}):
        broken = json.loads(json.dumps(raw)); broken["sections"][0].update(bad)
        path.write_text(json.dumps(broken), encoding="utf-8")
        with pytest.raises(ValueError):
            ExplanationScript.load(path)


def test_questionnaire_branches_without_scoring():
    flow = QuestionnaireFlow("Feedback", "clear", (
        {"id": "clear", "type": "number", "prompt": "Was this clear?", "branches": [{"operator": "lte", "value": 2, "target": "comment"}], "next": "done"},
        {"id": "comment", "type": "text", "prompt": "What should be clearer?", "next": "done"},
        {"id": "done", "type": "message", "prompt": "Thank you", "next": None},
    ))
    flow.validate()
    assert flow.next_id("clear", "1") == "comment"
    assert flow.next_id("clear", "5") == "done"


def test_api_answers_are_voiced_and_server_starts_without_beat_bank(monkeypatch):
    from fastapi.testclient import TestClient
    from virtual_physician import server

    def missing():
        raise ImportError("No module named 'numpy'")
    monkeypatch.setattr(server, "_beat_runtime", missing)
    app = server.create_app(str(EXAMPLES / "sources.jsonl"), str(EXAMPLES / "script.json"), llm_client=StubClient("Ask your clinical team about fasting [1]."))
    client = TestClient(app)
    assert client.get("/api/beat-library").json()["ready"] is False
    blocked = client.post("/api/beat-query", json={"text": "hello"})
    assert blocked.status_code == 503 and "prepare_beat_demo" in blocked.json()["error"]
    answer = client.post("/api/ask", json={"question": "Who confirms fasting questions?"}).json()
    assert answer["answer_mode"] == "rag-generation" and answer["spoken_text"] == "Ask your clinical team about fasting."
    channels = {event["channel"]: event for event in answer["events"]}
    assert channels["speech"]["value"] == answer["spoken_text"] and channels["expression"]["value"] == "happiness" and channels["gesture"]["value"] == "auto"
    declined = client.post("/api/ask", json={"question": "What is the capital of France?"}).json()
    assert declined["grounded"] is False and declined["emotion"] == "neutral"
    script = client.get("/api/script").json()
    assert script["personas"]["nurse"]["avatar"] == "mira" and script["sections"][2]["persona"] == "nurse"
