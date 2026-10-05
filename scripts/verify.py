"""Exercise the real FastAPI app with the bundled synthetic data contract.

Checks the authored script (personas, 7-emotion levels, authored/retrieved
gestures), grounded answers, the off-topic decline, the RAG generation path
and the questionnaire. Generation is exercised through the local-command
client with a deterministic stand-in command, which tests the plumbing and
citation checks only; configure --llm-endpoint/--llm-command for a real model.
"""
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from virtual_physician.generation import CommandClient
from virtual_physician.server import create_app

ROOT = Path(__file__).parents[1]
EXAMPLES = ROOT / "examples"
OUT = ROOT / "outputs" / "verify"
args = (str(EXAMPLES / "sources.jsonl"), str(EXAMPLES / "script.json"), str(EXAMPLES / "questionnaire.json"))
client = TestClient(create_app(*args))
# Stand-in "model": restates the first numbered passage and cites it.
stand_in = [sys.executable, "-c", "import json,sys;p=json.load(sys.stdin)['user'].split('\\n');print(p[3].split('. ')[0].strip()+'. [1]')"]
rag_client = TestClient(create_app(*args, llm_client=CommandClient(stand_in)))

home = client.get("/")
script = client.get("/api/script")
answer = client.post("/api/ask", json={"question": "Where should fasting questions be confirmed?"})
off_topic = client.post("/api/ask", json={"question": "What is the capital of France?"})
generated = rag_client.post("/api/ask", json={"question": "Where should fasting questions be confirmed?"})
beat = client.get("/api/beat-library")
form = client.get("/api/questionnaire")
branch = client.post("/api/questionnaire/respond", json={"item_id": "clear", "answer": "1"})
for response in (home, script, answer, off_topic, generated, beat, form, branch):
    response.raise_for_status()
payload, declined, rag = answer.json(), off_topic.json(), generated.json()
if not payload["grounded"] or not payload["citations"] or not payload["events"]:
    raise RuntimeError("API verify question did not return cited evidence and behavior events")
if declined["grounded"] or declined["citations"]:
    raise RuntimeError("off-topic question was not declined")
if rag["answer_mode"] != "rag-generation" or not rag["citations"]:
    raise RuntimeError(f"RAG generation path failed: {rag.get('answer_mode')} {rag.get('generation_error')}")
sections = script.json()["sections"]
artifacts = {
    "script.json": script.json(),
    "answer.json": payload,
    "answer-declined.json": declined,
    "answer-generated.json": rag,
    "questionnaire.json": form.json(),
    "questionnaire-branch.json": branch.json(),
}
OUT.mkdir(parents=True, exist_ok=True)
for name, data in artifacts.items():
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
if any(not (OUT / name).exists() for name in artifacts):
    raise RuntimeError("verify API artifacts were not written")
print(json.dumps({
    "title": script.json()["title"], "sections": len(sections),
    "section_delivery": [f"{s['persona']}:{s['emotion']}/{s['intensity']}:{s['gesture']}" for s in sections],
    "citation": payload["citations"][0]["source_id"], "off_topic_grounded": declined["grounded"],
    "generated_answer_mode": rag["answer_mode"], "answer_channels": sorted({event["channel"] for event in payload["events"]}),
    "beat_library_ready": beat.json().get("ready"), "questionnaire_branch": branch.json()["next_id"], "outputs": sorted(artifacts)}, indent=2))
