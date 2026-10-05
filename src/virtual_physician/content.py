from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

# The paper's seven emotions, each rendered at one of three intensity presets.
EMOTIONS = {"neutral", "anger", "disgust", "fear", "happiness", "sadness", "surprise"}

# Section 3.6: the patient can choose a doctor or a nurse character. Each
# persona binds a bundled avatar and a voice; scripts may override both.
DEFAULT_PERSONAS = {
    "doctor": {"label": "Doctor", "avatar": "rowan", "voice": {"language": "en-US", "pitch": 0.92, "rate": 0.98, "kokoro_voice": "af_heart"}},
    "nurse": {"label": "Nurse", "avatar": "mira", "voice": {"language": "en-US", "pitch": 1.12, "rate": 1.0, "kokoro_voice": "af_heart"}},
}
AVATARS = {"rowan", "mira"}
VOICE_NAME = re.compile(r"^[a-z]{2}_[a-z0-9]+$")


@dataclass(frozen=True)
class ScriptSection:
    id: str
    text: str
    emotion: str
    intensity: int
    gesture: str | None = None
    media_url: str | None = None
    media_alt: str | None = None
    video_url: str | None = None
    persona: str | None = None


def _https(value: str | None) -> bool:
    return not value or urlparse(value).scheme == "https"


def validate_personas(personas: dict) -> dict:
    merged = {name: {**value, "voice": dict(value["voice"])} for name, value in DEFAULT_PERSONAS.items()}
    for name, value in (personas or {}).items():
        if not isinstance(value, dict) or not re.fullmatch(r"[a-z][a-z0-9_-]*", str(name)):
            raise ValueError(f"persona '{name}' must be a lowercase name with an object value")
        base = merged.get(name, {"label": str(name).title(), "avatar": "rowan", "voice": {"language": "en-US"}})
        entry = {**base, **{k: v for k, v in value.items() if k != "voice"}, "voice": {**base["voice"], **(value.get("voice") or {})}}
        if entry["avatar"] not in AVATARS:
            raise ValueError(f"persona '{name}': avatar must be one of {sorted(AVATARS)}")
        voice = entry["voice"]
        if voice.get("kokoro_voice") and not VOICE_NAME.fullmatch(str(voice["kokoro_voice"])):
            raise ValueError(f"persona '{name}': kokoro_voice must look like 'af_heart'")
        for key, low, high in (("pitch", 0.1, 2.0), ("rate", 0.1, 2.0)):
            if key in voice and not low <= float(voice[key]) <= high:
                raise ValueError(f"persona '{name}': voice {key} must be between {low} and {high}")
        merged[name] = entry
    return merged


@dataclass(frozen=True)
class ExplanationScript:
    title: str
    reviewed_by: str
    reviewed_at: str
    sections: tuple[ScriptSection, ...]
    persona: str = "doctor"
    personas: dict = field(default_factory=dict)
    answer_emotion: dict = field(default_factory=lambda: {"emotion": "happiness", "intensity": 1})

    @classmethod
    def load(cls, path: str | Path) -> "ExplanationScript":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        script = cls(str(raw["title"]), str(raw["reviewed_by"]), str(raw["reviewed_at"]),
                     tuple(ScriptSection(**section) for section in raw["sections"]),
                     str(raw.get("persona", "doctor")), dict(raw.get("personas") or {}),
                     dict(raw.get("answer_emotion") or {"emotion": "happiness", "intensity": 1}))
        script.validate()
        return script

    @property
    def resolved_personas(self) -> dict:
        return validate_personas(self.personas)

    def persona_for(self, section: ScriptSection) -> str:
        return section.persona or self.persona

    def validate(self) -> None:
        if not self.title.strip() or not self.reviewed_by.strip():
            raise ValueError("title and reviewed_by are required")
        date.fromisoformat(self.reviewed_at)
        if not self.sections:
            raise ValueError("at least one explanation section is required")
        personas = self.resolved_personas
        if self.persona not in personas:
            raise ValueError(f"unknown script persona '{self.persona}'")
        if self.answer_emotion.get("emotion") not in EMOTIONS or self.answer_emotion.get("intensity") not in {1, 2, 3}:
            raise ValueError("answer_emotion needs one of the seven emotions and intensity 1, 2, or 3")
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
            if not _https(section.media_url):
                raise ValueError(f"{section.id}: media_url must be an HTTPS URL")
            if not _https(section.video_url):
                raise ValueError(f"{section.id}: video_url must be an HTTPS URL")
            if section.persona and section.persona not in personas:
                raise ValueError(f"{section.id}: unknown persona '{section.persona}'")
            if section.gesture is not None and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_ -]{0,40}", section.gesture):
                raise ValueError(f"{section.id}: gesture must be a short name such as 'open_hand', or 'auto'")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate clinician-authored virtual physician inputs")
    parser.add_argument("script")
    args = parser.parse_args()
    script = ExplanationScript.load(args.script)
    print(json.dumps({"title": script.title, "reviewed_by": script.reviewed_by, "sections": len(script.sections),
                      "personas": sorted({script.persona_for(section) for section in script.sections})}, indent=2))


if __name__ == "__main__":
    main()
