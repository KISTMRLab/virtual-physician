from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

EMOTIONS = {"neutral", "anger", "disgust", "fear", "happiness", "sadness", "surprise"}


@dataclass(frozen=True)
class ScriptSection:
    id: str
    text: str
    emotion: str
    intensity: int
    gesture: str
    media_url: str | None = None
    media_alt: str | None = None


@dataclass(frozen=True)
class ExplanationScript:
    title: str
    reviewed_by: str
    reviewed_at: str
    sections: tuple[ScriptSection, ...]

    @classmethod
    def load(cls, path: str | Path) -> "ExplanationScript":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        script = cls(str(raw["title"]), str(raw["reviewed_by"]), str(raw["reviewed_at"]), tuple(ScriptSection(**section) for section in raw["sections"]))
        script.validate()
        return script

    def validate(self) -> None:
        if not self.title.strip() or not self.reviewed_by.strip():
            raise ValueError("title and reviewed_by are required")
        date.fromisoformat(self.reviewed_at)
        if not self.sections:
            raise ValueError("at least one explanation section is required")
        ids: set[str] = set()
        for section in self.sections:
            if not section.id or section.id in ids:
                raise ValueError("section IDs must be non-empty and unique")
            ids.add(section.id)
            if not section.text.strip():
                raise ValueError(f"{section.id}: text is required")
            if section.emotion not in EMOTIONS:
                raise ValueError(f"{section.id}: unsupported emotion '{section.emotion}'")
            if section.intensity not in {1, 2, 3}:
                raise ValueError(f"{section.id}: intensity must be 1, 2, or 3")
            if section.media_url and urlparse(section.media_url).scheme != "https":
                raise ValueError(f"{section.id}: media_url must be an HTTPS URL")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate clinician-authored virtual physician inputs")
    parser.add_argument("script")
    args = parser.parse_args()
    script = ExplanationScript.load(args.script)
    print(json.dumps({"title": script.title, "reviewed_by": script.reviewed_by, "sections": len(script.sections)}, indent=2))


if __name__ == "__main__":
    main()
