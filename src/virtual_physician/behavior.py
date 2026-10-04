from __future__ import annotations

import re

from .content import ScriptSection


def plan_behavior(text: str, emotion: str = "neutral", intensity: int = 1, gesture: str = "open_hand") -> list[dict]:
    words = re.findall(r"[A-Za-z']+", text)
    events = [
        {"channel": "speech", "value": text, "at_ms": 0},
        {"channel": "expression", "value": emotion, "intensity": intensity / 3, "at_ms": 0},
        {"channel": "gesture", "value": gesture, "intensity": .75, "at_ms": 120},
    ]
    for index, word in enumerate(words):
        mouth = "open" if re.search(r"[aeiou]", word, re.I) else "narrow"
        events.append({"channel": "viseme", "value": mouth, "intensity": min(1.0, .4 + len(word) / 14), "at_ms": index * 190})
    return events


def section_payload(section: ScriptSection) -> dict:
    gesture = section.gesture or ("point_media" if section.media_url else "open_hand")
    return {"id": section.id, "text": section.text, "emotion": section.emotion, "intensity": section.intensity, "gesture": gesture, "media_url": section.media_url, "media_alt": section.media_alt, "events": plan_behavior(section.text, section.emotion, section.intensity, gesture)}

