#!/usr/bin/env python3
"""
Universelle Pipeline: URLs (Supabase) → Download → PNG → Gemini → Wissenstext → PDF.

Funktioniert mit beliebigen Dateien: User lädt im Frontend hoch → Supabase Bucket →
Backend bekommt Links → lädt runter, konvertiert zu PNG, schickt an Gemini 3 Flash,
erstellt Wissenstext, exportiert PDF.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def merge_corpus_to_wissenstext(corpus: str, *, model: str | None = None) -> str:
    """Aus Corpus (extrahierte Texte aus Gemini) einen kompakten Wissenstext erzeugen (OpenAI)."""
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY fehlt für Merge-Schritt")
    model = model or os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    client = OpenAI(api_key=api_key)
    max_chars = 90_000
    if len(corpus) > max_chars:
        corpus = "... [gekürzt] ...\n\n" + corpus[-max_chars:]
    prompt = f"""Aus den folgenden Dokument-Auszügen (aus verschiedenen Quellen extrahiert) erstelle EINEN kompakten, thematisch gegliederten Wissenstext für eine Wissensdatenbank / RAG-System.
Pro Abschnitt: Überschrift (## …), darunter Bullet-Points mit den relevanten Regeln/Fakten.
Keine Duplikate, keine Einzelfallbeispiele. Stil: sachlich, prägnant, auf Deutsch.

---
{corpus}
---
Dein Wissenstext:"""
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return (r.choices[0].message.content or "").strip()


def run_universal_pipeline(
    file_urls: list[str],
    output_dir: Path,
    *,
    gemini_model: str | None = None,
    openai_model: str | None = None,
    local_paths: list[Path] | None = None,
) -> Path:
    """
    URLs → Download → PNG → Gemini → Merge → PDF.
    Oder: local_paths=[Path(...)] für lokale Dateien (ohne Download).
    Returns: Pfad zur erzeugten PDF-Datei.
    """
    from convert_to_png import files_to_pngs
    from download_from_urls import download_from_urls
    from gemini_extract import extract_from_pngs
    from wissenstext_zu_pdf import build_pdf

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Dateien: Download von URLs oder lokale Pfade
    if local_paths:
        paths = [Path(p) for p in local_paths if Path(p).exists()]
    else:
        work_dir = output_dir / "work"
        work_dir.mkdir(exist_ok=True)
        _, paths = download_from_urls(file_urls, dest_dir=work_dir)
    if not paths:
        raise RuntimeError("Keine Dateien. URLs prüfen oder local_paths nutzen.")

    # 2. Alle Dateien → PNG(s)
    pngs = files_to_pngs(paths)
    if not pngs:
        raise RuntimeError("Keine PNGs aus den Dateien erzeugt.")

    # 3. Gemini: PNG → extrahierter Text
    extracted = extract_from_pngs(pngs, model=gemini_model)
    if not extracted:
        raise RuntimeError("Gemini lieferte keine Texte.")
    corpus = "\n\n".join(f"## Dokument: {name}\n\n{text}" for name, text in extracted)

    # 4. Merge zu Wissenstext (OpenAI)
    wissen_txt = merge_corpus_to_wissenstext(corpus, model=openai_model)
    wissen_path = output_dir / "Wissenstext.txt"
    wissen_path.write_text(wissen_txt, encoding="utf-8")

    # 5. PDF
    pdf_path = output_dir / "Wissenstext.pdf"
    build_pdf(wissen_path, pdf_path)
    return pdf_path


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Universelle Pipeline: URLs oder lokale Dateien → PDF")
    p.add_argument("--urls", nargs="*", help="Supabase-URLs der Dateien")
    p.add_argument("--local", nargs="+", metavar="PFAD", help="Lokale Dateipfade (statt URLs)")
    p.add_argument("--output", "-o", type=Path, default=Path("./output_universal"), help="Ausgabeordner")
    args = p.parse_args()
    if args.local:
        run_universal_pipeline([], args.output, local_paths=[Path(x) for x in args.local])
    elif args.urls:
        run_universal_pipeline(args.urls, args.output)
    else:
        p.error("--urls oder --local erforderlich")
    print(f"Fertig. PDF: {args.output / 'Wissenstext.pdf'}")
