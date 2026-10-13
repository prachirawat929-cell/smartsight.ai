# SmartSight AI

A hackathon prototype that simulates the core loop of assistive smart glasses: take a photo, detect everyday objects with a pretrained YOLO model, hear a short spoken description, and look things up on the web with the TinyFish Search and Fetch APIs.

> **Not a safety device.** SmartSight AI is a prototype, not a certified mobility aid. It works on single still photos. It cannot measure distance, judge whether something is in a person's path, prevent collisions, or help anyone through traffic. Never rely on it for safety.

## What it does

1. **Capture**: upload an image or take a still photo with your camera.
2. **Detect**: YOLOv8n (pretrained on the 80 COCO classes) finds people, chairs, bottles, bags, vehicles and more. Doors, stairs and signs are *not* COCO classes, so they will not be detected.
3. **Speak**: detections become one short sentence, such as "I can see 2 people and a chair." Repeated objects are grouped, and the sentence never makes claims about position or danger. Speech can be turned off, and the Replay button speaks it again.
4. **Look up**: pick a detected object or type a question. TinyFish Search returns ranked results, and TinyFish Fetch can read a result page as markdown.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # then put your key in .env
streamlit run app.py
```

Get a TinyFish key at <https://agent.tinyfish.ai/api-keys>. The key is read from `TINYFISH_API_KEY`. It is never hardcoded, displayed or logged. `.env` is git-ignored.

The first run downloads `yolov8n.pt` (about 6 MB).

### Speech notes

- Local speech uses `pyttsx3`, which needs a system engine: SAPI5 (Windows) and NSSpeech (macOS) work out of the box; on Linux install `espeak-ng`.
- If `pyttsx3` is unavailable (for example on a hosted deployment), the app falls back to your browser's built-in speech synthesis when you press Replay or a "Read aloud" button. Browsers may block audio that did not start from a click.

## TinyFish integration

Verified against the TinyFish docs (October 2026).

| | Search | Fetch |
|---|---|---|
| Endpoint | `GET https://api.search.tinyfish.ai` | `POST https://api.fetch.tinyfish.ai` |
| Auth | `X-API-Key` header | `X-API-Key` header |
| Input | `query` parameter (optional `location`, `language`, `page`, …) | JSON `{"urls": [...], "format": "markdown"}` (1–10 URLs) |
| Output used | `results[]`: `title`, `snippet`, `url`, `site_name` | `results[]`: `title`, `text`, `final_url`; `errors[]`: `url`, `error` |

Fetch can fail for a single URL while the HTTP call still succeeds. Those failures appear in `errors[]` (for example `bot_blocked`, `login_required`), and the app reports them. Search is rate limited to 30 requests per minute by default.

## Project layout

```
app.py                 Streamlit UI
detector.py            YOLO detection + annotated image
speech.py              Detections -> sentence, TTS helpers
tinyfish_client.py     Search + Fetch client
tests/test_core.py     Unit tests (no network, no model download)
```

Run the tests with `pytest`.

## Limitations

- Still images only. There is no live video, no depth or distance, and no tracking.
- 80 COCO classes only. Accuracy drops with blur, low light and unusual angles.
- Web results are shown as returned by TinyFish and are not verified for accuracy.
- Detection confidence thresholds are a trade-off. Lower values add false positives, higher values miss objects.

## Ideas for next steps

- Add an OCR mode for reading labels and signs.
- Add a text-to-speech option that works better on hosted deployments.
- Test with blind and low-vision users before making any usability claims.
