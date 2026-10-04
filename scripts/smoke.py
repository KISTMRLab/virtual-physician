"""Exercise the real FastAPI app with the bundled synthetic data contract."""
import json
from pathlib import Path

from fastapi.testclient import TestClient
from virtual_physician.server import create_app

ROOT = Path(__file__).parents[1]
EXAMPLES = ROOT / "examples"
OUT = ROOT / "outputs" / "smoke"
app = create_app(str(EXAMPLES / "sources.jsonl"), str(EXAMPLES / "script.json"), str(EXAMPLES / "questionnaire.json"))
client = TestClient(app)

home = client.get("/")
script = client.get("/api/script")
answer = client.post("/api/ask", json={"question": "Where should fasting questions be confirmed?"})
form = client.get("/api/questionnaire")
branch = client.post("/api/questionnaire/respond", json={"item_id": "clear", "answer": "1"})
for response in (home, script, answer, form, branch):
    response.raise_for_status()
payload = answer.json()
if not payload["grounded"] or not payload["citations"] or not payload["events"]:
    raise RuntimeError("API smoke question did not return cited evidence and behavior events")
artifacts = {
    "script.json": script.json(),
    "answer.json": payload,
    "questionnaire.json": form.json(),
    "questionnaire-branch.json": branch.json(),
}
OUT.mkdir(parents=True, exist_ok=True)
for name, data in artifacts.items():
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
if any(not (OUT / name).exists() for name in artifacts):
    raise RuntimeError("smoke API artifacts were not written")
print(json.dumps({"title": script.json()["title"], "sections": len(script.json()["sections"]), "citation": payload["citations"][0]["source_id"], "behavior_channels": sorted({event["channel"] for event in payload["events"]}), "questionnaire_branch": branch.json()["next_id"], "outputs": sorted(artifacts)}, indent=2))
