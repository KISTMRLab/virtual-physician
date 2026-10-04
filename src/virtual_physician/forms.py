from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class QuestionnaireFlow:
    title: str
    start_id: str
    items: tuple[dict, ...]

    @classmethod
    def load(cls, path: str | Path) -> "QuestionnaireFlow":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        flow = cls(str(raw["title"]), str(raw["start_id"]), tuple(raw["items"]))
        flow.validate()
        return flow

    def validate(self) -> None:
        ids = {item.get("id") for item in self.items}
        if self.start_id not in ids:
            raise ValueError("start_id must name an item")
        for item in self.items:
            if not item.get("prompt") or item.get("type") not in {"choice", "number", "text", "message"}:
                raise ValueError(f"invalid questionnaire item: {item.get('id')}")
            if any(key in item for key in ("diagnosis", "risk_score", "clinical_score")):
                raise ValueError("diagnostic or clinical scoring fields are not supported")
            targets = [item.get("next"), *(branch.get("target") for branch in item.get("branches", []))]
            if any(target and target not in ids for target in targets):
                raise ValueError(f"{item['id']}: branch target does not exist")

    def item(self, item_id: str) -> dict | None:
        return next((item for item in self.items if item["id"] == item_id), None)

    def next_id(self, item_id: str, answer: str) -> str | None:
        item = self.item(item_id)
        if item is None:
            raise ValueError("unknown questionnaire item")
        for branch in item.get("branches", []):
            operator, expected = branch.get("operator"), branch.get("value")
            if operator == "eq" and str(answer) == str(expected):
                return branch["target"]
            if operator in {"gte", "lte"}:
                try:
                    matched = float(answer) >= float(expected) if operator == "gte" else float(answer) <= float(expected)
                except (ValueError, TypeError):
                    matched = False
                if matched:
                    return branch["target"]
        return item.get("next")
