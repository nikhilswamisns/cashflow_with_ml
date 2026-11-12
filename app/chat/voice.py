"""Speech to text for the chat mic button: audio in, text out, via OpenAI Whisper. The key comes from .env and is never logged.
`post` is injectable so tests run without the network."""
from __future__ import annotations

import os

import dotenv
import httpx

URL = "https://api.openai.com/v1/audio/transcriptions"
MAX_BYTES = 10 * 1024 * 1024
# Spelling hints: Whisper leans toward these words, so company terms and names are not misheard.
VOCAB = "Gutster cash flow forecast. SERVPRO, Aramsco, DSO, DPO, A/R, A/P, receivables, payables, payroll, invoices, overdue, AI model."


def _default_post(data: bytes, filename: str, content_type: str, key: str, model: str) -> dict:
    r = httpx.post(URL, headers={"Authorization": f"Bearer {key}"}, timeout=60,
                   files={"file": (filename, data, content_type)},
                   data={"model": model, "language": "en", "prompt": VOCAB, "temperature": "0"})
    r.raise_for_status()
    return r.json()


def transcribe(data: bytes, filename: str = "audio.webm", content_type: str = "audio/webm", post=None) -> dict:
    """{'text': str} or {'error': str}."""
    if not data:
        return {"error": "No audio was recorded."}
    if len(data) > MAX_BYTES:
        return {"error": "That recording is too long. Keep it under a minute."}
    dotenv.load_dotenv()
    key = os.environ.get("OPENAI_API_KEY", "")
    if post is None and (not key or key == "open-ai-key"):
        return {"error": "OPENAI_API_KEY is not set on this server."}
    model = os.environ.get("OPENAI_TRANSCRIBE_MODEL", "whisper-1")
    try:
        out = (post or (lambda *a: _default_post(*a, key, model)))(data, filename, content_type)
    except httpx.HTTPError:
        return {"error": "The speech service did not answer. Try again."}
    text = str(out.get("text") or "").strip()
    return {"text": text} if text else {"error": "I could not hear anything. Try again closer to the microphone."}
