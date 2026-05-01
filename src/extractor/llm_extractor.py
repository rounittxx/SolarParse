# Gemini-powered extraction.
# Strategy:
#   - Send the bill image(s) directly to gemini-1.5-flash (vision)
#   - If we also have a text layer, attach it as an extra hint
#   - Force JSON output with response_mime_type="application/json"
#   - Validate every field, coerce numerics, never let the model invent values
#
# We use Flash, not Pro, because:
#   1. it's free-tier friendly
#   2. it's ~5x faster
#   3. extraction is a structured task, not a reasoning task

import io
import json
import os
import re

from PIL import Image

from src.config import FIELDS, FIELD_KEYS


SYSTEM_PROMPT = """You are an expert at reading Indian electricity bills (MSEDCL, BEST, Tata Power, Adani, etc.).

Extract ONLY the fields listed in the JSON schema below from the bill in the image.

Hard rules:
- Output a single JSON object. No prose, no markdown fences.
- If a field is not clearly visible in the bill, set it to null. NEVER guess.
- Numeric fields must be numbers, not strings (no commas, no units).
- For each extracted field, also return a "confidence" between 0 and 1
  reflecting how confident you are the value is correct.

Return shape:
{
  "fields": {
    "<field_key>": <value or null>,
    ...
  },
  "confidence": {
    "<field_key>": <0..1>,
    ...
  }
}

Field meanings:
"""


def _build_prompt() -> str:
    schema_lines = []
    for f in FIELDS:
        unit = f" [{f.unit}]" if f.unit else ""
        schema_lines.append(f"  - {f.key}{unit}: {f.hint}")
    return SYSTEM_PROMPT + "\n".join(schema_lines)


def _coerce_number(v):
    """Pull a float out of '1,234.56' / 'Rs 1234' / '4.0 kW' style strings."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def _normalise(payload: dict) -> dict:
    """Turn whatever the model returned into the shape the rest of the app expects."""
    fields = payload.get("fields", {}) if isinstance(payload, dict) else {}
    confs = payload.get("confidence", {}) if isinstance(payload, dict) else {}

    numeric_keys = {"units_consumed", "total_bill_amount", "connected_load", "sanctioned_load"}

    cleaned = {}
    for k in FIELD_KEYS:
        v = fields.get(k)
        if v in ("", "N/A", "n/a", "null", "None"):
            v = None
        if k in numeric_keys:
            v = _coerce_number(v)
        cleaned[k] = v

    cleaned_conf = {}
    for k in FIELD_KEYS:
        c = confs.get(k, 0.0)
        try:
            c = float(c)
        except (TypeError, ValueError):
            c = 0.0
        # if a value is missing, drop confidence to 0 so we don't show a green chip on null
        if cleaned[k] in (None, ""):
            c = 0.0
        cleaned_conf[k] = max(0.0, min(1.0, c))

    return {"fields": cleaned, "confidence": cleaned_conf}


def extract_with_gemini(images: list[Image.Image], text_hint: str = "") -> dict:
    """
    images: page images of the bill
    text_hint: anything we already pulled from the PDF text layer (optional, helps a lot)

    Returns: {"fields": {...}, "confidence": {...}}
    """
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY (or GEMINI_API_KEY) not set. "
            "Get one free at https://aistudio.google.com/apikey and add it to .env"
        )

    # Imported here so the rest of the app still loads if the package
    # isn't installed (useful during tests with mocks).
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.0,
        },
    )

    parts = [_build_prompt()]
    if text_hint.strip():
        parts.append("Text layer pulled from the PDF (use as a hint, image is the source of truth):\n\n" + text_hint[:6000])
    parts.extend(images or [])

    if not images and not text_hint.strip():
        raise ValueError("Nothing to send to Gemini -- no images and no text.")

    resp = model.generate_content(parts)
    raw = resp.text or "{}"

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # last-ditch: pull the first {...} blob out of the response
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        payload = json.loads(m.group()) if m else {}

    return _normalise(payload)


# --- offline / test helper -------------------------------------------------

def extract_from_text_only(text: str) -> dict:
    """
    Used by the test suite and by the 'no API key' fallback path.
    Tries a few obvious regexes against MSEDCL-style bills. Cheap, dumb,
    and surprisingly often right.
    """
    out = {k: None for k in FIELD_KEYS}
    conf = {k: 0.0 for k in FIELD_KEYS}

    def grab(pattern, key, group=1, cast=None, c=0.6):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            v = m.group(group).strip()
            if cast:
                try:
                    v = cast(v.replace(",", ""))
                except ValueError:
                    return
            out[key] = v
            conf[key] = c

    grab(r"consumer\s*(?:no|number|n[o0])\s*[:\-]?\s*([A-Z0-9\-]+)", "consumer_number")
    grab(r"meter\s*(?:no|number)\s*[:\-]?\s*([A-Z0-9\-]+)", "meter_number")
    grab(r"units?\s*consumed\s*[:\-]?\s*([\d,]+(?:\.\d+)?)", "units_consumed", cast=float)
    grab(r"(?:total|net|amount\s*payable)\s*[:\-]?\s*(?:rs\.?|₹|inr)?\s*([\d,]+(?:\.\d+)?)", "total_bill_amount", cast=float)
    grab(r"connected\s*load\s*[:\-]?\s*([\d.]+)", "connected_load", cast=float)
    grab(r"sanctioned\s*load\s*[:\-]?\s*([\d.]+)", "sanctioned_load", cast=float)
    grab(r"tariff\s*(?:category|code)?\s*[:\-]?\s*([A-Z0-9\-\s]+?)(?:\n|$)", "tariff_category")
    grab(r"bill(?:ing)?\s*(?:period|month)\s*[:\-]?\s*([A-Za-z0-9 \-/,]+?)(?:\n|$)", "billing_period")

    return {"fields": out, "confidence": conf}
