from __future__ import annotations

from .content import ExplanationScript, ScriptSection

AUTO_GESTURE = "auto"


def plan_behavior(text: str, emotion: str = "neutral", intensity: int = 1, gesture: str | None = AUTO_GESTURE) -> list[dict]:
    """Parallel speech, expression, gesture and lip-sync events for one utterance.

    ``expression`` carries the emotion name and its 1-3 preset level, which the
    browser passes unchanged to the renderer. ``gesture`` is either an authored
    override (played as a named pose) or ``auto`` (recorded co-speech motion
    retrieved for the spoken text). The single ``viseme`` event asks the
    renderer's speech path to derive phoneme visemes from the same text.
    """
    level = int(intensity)
    gesture = gesture or AUTO_GESTURE
    return [
        {"channel": "speech", "value": text, "at_ms": 0},
        {"channel": "expression", "value": emotion, "level": level, "intensity": round(level / 3, 4), "at_ms": 0},
        {"channel": "gesture", "value": gesture, "source": "retrieval" if gesture == AUTO_GESTURE else "authored", "at_ms": 0},
        {"channel": "viseme", "value": "text-phonemes", "source": "speech-text", "at_ms": 0},
    ]


def section_payload(section: ScriptSection, script: ExplanationScript | None = None) -> dict:
    gesture = section.gesture or AUTO_GESTURE
    persona = script.persona_for(section) if script else (section.persona or "doctor")
    return {"id": section.id, "text": section.text, "emotion": section.emotion, "intensity": section.intensity,
            "gesture": gesture, "gesture_source": "retrieval" if gesture == AUTO_GESTURE else "authored",
            "media_url": section.media_url, "media_alt": section.media_alt, "video_url": section.video_url,
            "persona": persona, "events": plan_behavior(section.text, section.emotion, section.intensity, gesture)}
