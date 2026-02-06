#!/usr/bin/env python3
"""
Extraktion von Text/Struktur aus Dokument-Bildern (PNG) via Gemini 3 Flash Preview.

Sendet PNG(s) an die Google Gemini API und erhält strukturierten Markdown-Text
für die weitere Wissensbasis-Verarbeitung.
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = types = None

MODEL = "gemini-2.5-flash"
BATCH_SIZE = 5  # max PNGs pro API-Call (Token-Limit)
PAUSE_SEC = 1.0
MAX_RETRIES = 2

PROMPT = """Extrahiere aus diesem Dokument alle Texte und Strukturen für eine Wissensbasis (RAG).
Ausgabe: Klares Markdown mit Abschnitten. Nur Fakten, Regeln, Informationen – keine Einleitung, keine Duplikate.
Bei Tabellen: als lesbare Struktur. Bei Listen: als Bullet-Points."""


def extract_from_pngs(
    pngs: list[tuple[str, bytes]],
    *,
    model: str | None = None,
    api_key: str | None = None,
) -> list[tuple[str, str]]:
    """
    Sendet PNGs an Gemini 3 Flash Preview, erhält extrahierten Text.
    Returns: [(source_name, extracted_text), ...]
    """
    if not genai or not types:
        raise RuntimeError("google-genai nicht installiert: pip install google-genai")
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY fehlt (z. B. in .env)")
    model = model or os.environ.get("GEMINI_MODEL", MODEL)
    client = genai.Client(api_key=api_key)
    results = []
    for i in range(0, len(pngs), BATCH_SIZE):
        batch = pngs[i : i + BATCH_SIZE]
        contents = []
        for name, png_bytes in batch:
            contents.append(types.Part.from_bytes(data=png_bytes, mime_type="image/png"))
        contents.append(f"[Quelle(n): {', '.join(n for n, _ in batch)}]\n\n{PROMPT}")
        for attempt in range(MAX_RETRIES + 1):
            try:
                r = client.models.generate_content(model=model, contents=contents)
                text = (r.text or "").strip()
                if text:
                    source = " | ".join(n for n, _ in batch)
                    results.append((source, text))
                break
            except Exception as e:
                if attempt < MAX_RETRIES:
                    time.sleep(3)
                    continue
                raise RuntimeError(f"Gemini API Fehler: {e}") from e
        time.sleep(PAUSE_SEC)
    return results
