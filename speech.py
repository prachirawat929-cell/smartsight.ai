"""Turn detections into short spoken sentences, and produce audio for them.

The wording deliberately avoids spatial or safety claims ("in front of you",
"blocking your path", distances). A 2D photo detector cannot support those.
"""
from __future__ import annotations

import os
import tempfile
from collections import Counter
from typing import Iterable

IRREGULAR_PLURALS = {
    "person": "people",
    "knife": "knives",
    "sheep": "sheep",
    "scissors": "scissors",
    "skis": "skis",
    "broccoli": "broccoli",
    "tv": "TVs",
    "potted plant": "potted plants",
    "hair drier": "hair dryers",
    "wine glass": "wine glasses",
    "sandwich": "sandwiches",
    "couch": "couches",
    "bench": "benches",
    "toothbrush": "toothbrushes",
    "traffic light": "traffic lights",
}
MASS_OR_PLURAL_ONLY = {"scissors", "skis", "sheep", "broccoli"}
MAX_DISTINCT_SPOKEN = 5
NO_OBJECTS_MESSAGE = "I couldn't identify any supported objects in this image."


def _pluralize(label: str) -> str:
    if label in IRREGULAR_PLURALS:
        return IRREGULAR_PLURALS[label]
    if label.endswith(("s", "x", "ch", "sh")):
        return label + "es"
    return label + "s"


def _phrase(label: str, count: int) -> str:
    if count == 1:
        if label in {"scissors", "skis"}:
            return label
        article = "an" if label[0].lower() in "aeiou" else "a"
        return f"{article} {label}"
    return f"{count} {_pluralize(label)}"


def _join(parts: list[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def describe_detections(labels: Iterable[str]) -> str:
    """Build one concise sentence from a list of detected class labels."""
    counts = Counter(l.strip().lower() for l in labels if l and l.strip())
    if not counts:
        return NO_OBJECTS_MESSAGE
    # Most frequent first, then alphabetical for stable output.
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    shown, rest = ordered[:MAX_DISTINCT_SPOKEN], ordered[MAX_DISTINCT_SPOKEN:]
    parts = [_phrase(label, n) for label, n in shown]
    if rest:
        extra = sum(n for _, n in rest)
        parts.append(f"{extra} other {'object' if extra == 1 else 'objects'}")
    return f"I can see {_join(parts)}."


def synthesize_wav(text: str) -> bytes | None:
    """Render `text` to WAV bytes with pyttsx3 (offline). Returns None if unavailable.

    pyttsx3 needs a system speech engine (SAPI5 on Windows, NSSpeech on macOS,
    espeak-ng on Linux). On failure the app falls back to browser speech.
    """
    path = None
    try:
        import pyttsx3

        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.save_to_file(text, path)
        engine.runAndWait()
        engine.stop()
        if os.path.getsize(path) == 0:
            return None
        with open(path, "rb") as fh:
            return fh.read()
    except Exception:
        return None
    finally:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


def browser_speech_html(text: str) -> str:
    """HTML snippet that speaks `text` using the browser's built-in speechSynthesis."""
    import json

    payload = json.dumps(text)
    return (
        "<script>"
        "try{window.speechSynthesis.cancel();"
        f"const u=new SpeechSynthesisUtterance({payload});"
        "u.rate=0.95;window.speechSynthesis.speak(u);}catch(e){}"
        "</script>"
    )
