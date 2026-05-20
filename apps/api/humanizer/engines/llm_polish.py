"""Gemini Flash 3.5 polish engine.

Final-pass humanizer that takes the already-cleaned + lexically + structurally
transformed text and asks Gemini Flash 3.5 to rewrite it in a more human voice
while preserving meaning, facts, names, and formatting.

Why Gemini Flash 3.5 (released 2026-05-19):
- ~3x cheaper than competitor flagships
- 1M token context window (handles full articles)
- Strong rewrite/style transfer per benchmarks

No external SDK — uses stdlib `urllib.request` to avoid adding `google-generativeai`
to the dependency tree. Async I/O via `asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Final

log = logging.getLogger(__name__)

GEMINI_MODEL: Final[str] = "gemini-3.5-flash"
GEMINI_ENDPOINT: Final[str] = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)
TIMEOUT_SECONDS: Final[float] = 30.0

# Strength → generation_config knobs
_STRENGTH_CONFIG: dict[str, dict[str, float]] = {
    "light": {"temperature": 0.4, "topP": 0.85},
    "medium": {"temperature": 0.7, "topP": 0.9},
    "aggressive": {"temperature": 0.95, "topP": 0.95},
}


_SYSTEM_PROMPT_EN = """You are a human writing assistant. You will receive text \
that has already been processed by a statistical humanizer. Your job is the FINAL \
polish pass: rewrite the text so it reads as if a thoughtful human author wrote it \
in their own voice.

STRICT RULES:
1. PRESERVE every fact, claim, number, name, brand, URL, email, and code block exactly.
2. PRESERVE the original meaning. Do NOT add new claims or remove existing ones.
3. PRESERVE structure: headings, bullet points, numbered lists, paragraph breaks.
4. PRESERVE markdown formatting (bold, italic, links, code) verbatim.
5. Vary sentence length and openers. Avoid AI tells like "delve", "leverage", \
"furthermore", "moreover", "in conclusion", "it's important to note".
6. Use contractions naturally where they fit (don't, won't, it's).
7. Write at a natural human cadence — some short sentences, some longer.
8. Do NOT add disclaimers, meta-commentary, or "Here's the rewritten text:" prefixes.
9. Output ONLY the rewritten text, nothing else.
"""

_SYSTEM_PROMPT_HE = """אתה עוזר כתיבה אנושי. תקבל טקסט שעבר עיבוד סטטיסטי \
ל"האנשה". התפקיד שלך הוא מעבר ליטוש סופי: לכתוב מחדש את הטקסט כך שיקרא כאילו \
אדם מהורהר כתב אותו בקול שלו.

חוקים מחייבים:
1. שמור על כל עובדה, מספר, שם, מותג, URL, אימייל ובלוק קוד בדיוק כפי שהם.
2. שמור על המשמעות המקורית. אל תוסיף או תסיר טענות.
3. שמור על המבנה: כותרות, נקודות, רשימות ממוספרות, מעברי פסקה.
4. שמור על עיצוב markdown (מודגש, נטוי, קישורים, קוד) כפי שהוא.
5. גוון את אורך המשפטים ואת פתיחי המשפטים. הימנע מסימני AI כמו "להעמיק", "למנף", \
"יתרה מכך", "לסיכום", "חשוב לציין".
6. כתוב בקצב אנושי טבעי — חלק קצר, חלק ארוך.
7. אל תוסיף הסתייגויות, פרשנות מטא, או "הנה הטקסט הכתוב מחדש:" כפתיח.
8. הוצא רק את הטקסט הכתוב מחדש, ללא שום דבר נוסף.
"""


@dataclass
class LLMPolishResult:
    text: str
    model: str
    prompt_tokens: int | None = None
    output_tokens: int | None = None


class LLMPolishError(RuntimeError):
    """Raised when Gemini call fails or returns no usable content."""


def _build_payload(text: str, language: str, strength: str) -> dict:
    system = _SYSTEM_PROMPT_HE if language == "he" else _SYSTEM_PROMPT_EN
    gen_cfg = _STRENGTH_CONFIG.get(strength, _STRENGTH_CONFIG["medium"])
    return {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [
            {
                "role": "user",
                "parts": [{"text": text}],
            }
        ],
        "generationConfig": {
            "temperature": gen_cfg["temperature"],
            "topP": gen_cfg["topP"],
            "maxOutputTokens": 8192,
            "responseMimeType": "text/plain",
        },
        "safetySettings": [
            {"category": c, "threshold": "BLOCK_ONLY_HIGH"}
            for c in (
                "HARM_CATEGORY_HARASSMENT",
                "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "HARM_CATEGORY_DANGEROUS_CONTENT",
            )
        ],
    }


def _call_gemini_sync(api_key: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    url = f"{GEMINI_ENDPOINT}?key={api_key}"
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:
            detail = "<no body>"
        raise LLMPolishError(f"gemini_http_{e.code}: {detail[:400]}") from e
    except urllib.error.URLError as e:
        raise LLMPolishError(f"gemini_network_error: {e.reason}") from e
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise LLMPolishError(f"gemini_invalid_json: {raw[:200]!r}") from e


def _extract_text(response: dict) -> str:
    candidates = response.get("candidates") or []
    if not candidates:
        block = response.get("promptFeedback", {}).get("blockReason")
        raise LLMPolishError(
            f"gemini_no_candidates"
            + (f" (blocked: {block})" if block else "")
        )
    parts = candidates[0].get("content", {}).get("parts") or []
    text_parts = [p.get("text", "") for p in parts if isinstance(p, dict)]
    out = "".join(text_parts).strip()
    if not out:
        finish = candidates[0].get("finishReason")
        raise LLMPolishError(f"gemini_empty_output (finishReason={finish})")
    return out


async def polish(
    text: str,
    language: str,
    strength: str,
    api_key: str,
) -> LLMPolishResult:
    """Polish `text` with Gemini Flash 3.5. Returns LLMPolishResult.

    Raises LLMPolishError on any failure (HTTP, parsing, empty output, safety block).
    """
    if not api_key:
        raise LLMPolishError("gemini_api_key_missing")
    payload = _build_payload(text, language, strength)
    response = await asyncio.to_thread(_call_gemini_sync, api_key, payload)
    polished = _extract_text(response)
    usage = response.get("usageMetadata") or {}
    return LLMPolishResult(
        text=polished,
        model=GEMINI_MODEL,
        prompt_tokens=usage.get("promptTokenCount"),
        output_tokens=usage.get("candidatesTokenCount"),
    )
