#!/usr/bin/env python3
"""
Skalierbare Pipeline: E-Mails oder Paare → Wissenstext-PDF für die Wissensdatenbank.

Ein Kunde legt seine Daten in einen Ordner (oder eine Datei) und erhält am Ende
ein PDF, das in die Wissensdatenbank eines KI-Agenten kann.

Eingabe (--input):
  • Ordner mit Unterordnern „posteingang“ und „postausgang“ (jeweils .eml-Dateien)
    → E-Mails werden per Message-ID/In-Reply-To gepaart, dann volle Pipeline.
  • Ordner mit einer Datei „paare.txt“ (Format: „--- Paar N ---“, „[ Anfrage / Kunde ]“, „[ Antwort / Reiseteam ]“)
    → Paare werden direkt genutzt, Rest der Pipeline läuft.
  • Einzelne Datei „paare.txt“ oder „*.txt“ im gleichen Format
    → wie oben.

Ausgabe (--output):
  Alle Zwischenergebnisse und das finale PDF liegen im Ausgabeordner:
  paare.txt, paare_strukturiert.json, KI_Wissensextraktion.md, Wissenstext.txt, Wissenstext.pdf

Beispiele:
  python pipeline_wissenstext.py --input ./projekte/kunde_xyz --output ./projekte/kunde_xyz/output
  python pipeline_wissenstext.py --input ./meine_mails --output ./out --support-domain firma.com
"""

import argparse
import sys
from pathlib import Path

# Projektroot = Ordner dieses Skripts
BASE = Path(__file__).resolve().parent


def detect_input(input_path: Path) -> tuple[str, Path | None, Path | None, Path | None]:
    """
    Erkennt den Eingabetyp.
    Returns: ("eml"|"paare"|"md_wissen", posteingang_dir, postausgang_dir, paare_file)
    Bei "eml": posteingang_dir und postausgang_dir sind gesetzt.
    Bei "paare": paare_file ist gesetzt.
    Bei "md_wissen": nur für spätere Erweiterung (direkt MD mit ## Paar).
    """
    input_path = input_path.resolve()
    if input_path.is_file():
        if input_path.suffix.lower() in (".txt", ".md"):
            content = input_path.read_text(encoding="utf-8", errors="replace")
            if "--- Paar " in content and "[ Anfrage / Kunde ]" in content and "[ Antwort / Reiseteam ]" in content:
                return ("paare", None, None, input_path)
            if content.strip().startswith("# ") and "## Paar " in content:
                return ("md_wissen", None, None, input_path)  # später: direkt Wissenstext-Stufe
        return ("unknown", None, None, None)

    # Ordner: Suche posteingang / postausgang (exakt oder im Namen) oder paare.txt
    posteingang = postausgang = paare_file = None
    for d in input_path.iterdir():
        if not d.is_dir():
            continue
        if not any(d.glob("*.eml")):
            continue
        name_lower = d.name.lower()
        if "posteingang" in name_lower or name_lower in ("in", "eingang"):
            posteingang = d
        elif "postausgang" in name_lower or name_lower in ("out", "ausgang"):
            postausgang = d
    for candidate in ("paare.txt", "Wissensbasis_Reiseteam_141_Paare.txt"):
        f = input_path / candidate
        if f.is_file():
            paare_file = f
            break
    if not paare_file and input_path.is_dir():
        for f in input_path.glob("*.txt"):
            try:
                t = f.read_text(encoding="utf-8", errors="replace")[:2000]
                if "--- Paar " in t and "[ Anfrage / Kunde ]" in t:
                    paare_file = f
                    break
            except Exception:
                pass

    if posteingang and postausgang:
        return ("eml", posteingang, postausgang, None)
    if paare_file:
        return ("paare", None, None, paare_file)
    return ("unknown", None, None, None)


def run_pipeline(
    input_path: Path,
    output_dir: Path,
    support_domain: str | None = None,
    skip_llm_extract: bool = False,
    skip_llm_compress: bool = False,
) -> Path | None:
    """
    Führt die volle Pipeline aus. Gibt den Pfad zur erzeugten PDF-Datei zurück oder None bei Fehler.
    skip_llm_*: für Tests ohne API (dann müssen die Zwischendateien schon existieren).
    """
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    kind, posteingang, postausgang, paare_file = detect_input(input_path)
    if kind == "unknown":
        print("FEHLER: Eingabe nicht erkannt. Erwartet: Ordner mit posteingang/ + postausgang/ (.eml) oder paare.txt.", file=sys.stderr)
        return None
    if kind == "md_wissen":
        print("Hinweis: Direkt MD mit „## Paar“ als Eingabe noch nicht implementiert. Bitte paare.txt oder E-Mail-Ordner nutzen.", file=sys.stderr)
        return None

    paare_txt = output_dir / "paare.txt"
    if kind == "eml":
        from email_analyse import run_with_paths as run_email
        n = run_email(
            posteingang,
            postausgang,
            paare_txt,
            output_dir / "Analyse_Bericht.txt",
            support_domain=support_domain,
        )
        if n == 0:
            print("Warnung: Keine E-Mail-Paare gefunden. Prüfen Sie posteingang/postausgang und Support-Domain.", file=sys.stderr)
    elif kind == "paare":
        if paare_file.resolve() != paare_txt.resolve():
            paare_txt.write_bytes(paare_file.read_bytes())
        paare_txt = output_dir / "paare.txt"

    # Paare → JSON
    from wissen_analyse_parser import run_with_paths as run_parser
    paare_json = output_dir / "paare_strukturiert.json"
    run_parser(paare_txt, paare_json)

    ki_md = output_dir / "KI_Wissensextraktion.md"
    if not skip_llm_extract:
        from llm_wissensextraktion import run_with_paths as run_llm_extract
        if run_llm_extract(paare_json, ki_md) != 0:
            return None
    elif not ki_md.exists():
        print("FEHLER: KI_Wissensextraktion.md fehlt und skip_llm_extract ist gesetzt.", file=sys.stderr)
        return None

    wissen_txt = output_dir / "Wissenstext.txt"
    if not skip_llm_compress:
        from llm_wissenstext_aus_md import run_with_paths as run_llm_compress
        run_llm_compress(ki_md, wissen_txt)
    elif not wissen_txt.exists():
        print("FEHLER: Wissenstext.txt fehlt und skip_llm_compress ist gesetzt.", file=sys.stderr)
        return None

    pdf_path = output_dir / "Wissenstext.pdf"
    from wissenstext_zu_pdf import build_pdf
    build_pdf(wissen_txt, pdf_path)
    return pdf_path


def main() -> None:
    p = argparse.ArgumentParser(
        description="Pipeline: E-Mails oder Paare → Wissenstext-PDF für Wissensdatenbank",
        epilog="Eingabe: Ordner mit posteingang/ + postausgang/ (.eml) oder paare.txt. Ausgabe: Ordner mit PDF und Zwischendateien.",
    )
    p.add_argument("--input", "-i", type=Path, required=True, help="Ordner mit E-Mails oder paare.txt / Pfad zu paare.txt")
    p.add_argument("--output", "-o", type=Path, help="Ausgabeordner (Standard: <input>/output)")
    p.add_argument("--support-domain", type=str, default="", help="E-Mail-Domain des Supports (z.B. unyflygroup.com) für E-Mail-Pairing")
    p.add_argument("--skip-llm-extract", action="store_true", help="KI-Extraktion überspringen (paare_strukturiert.json → KI_Wissensextraktion.md muss existieren)")
    p.add_argument("--skip-llm-compress", action="store_true", help="Kompression überspringen (KI_Wissensextraktion.md → Wissenstext.txt muss existieren)")
    args = p.parse_args()

    input_path = args.input.resolve()
    if not input_path.exists():
        print(f"FEHLER: Eingabe existiert nicht: {input_path}", file=sys.stderr)
        sys.exit(1)
    output_dir = (args.output or (input_path / "output" if input_path.is_dir() else input_path.parent / "output")).resolve()
    support_domain = args.support_domain.strip() or None

    pdf_path = run_pipeline(
        input_path,
        output_dir,
        support_domain=support_domain,
        skip_llm_extract=args.skip_llm_extract,
        skip_llm_compress=args.skip_llm_compress,
    )
    if pdf_path is None:
        sys.exit(1)
    print(f"\nPipeline fertig. PDF: {pdf_path}")


if __name__ == "__main__":
    main()
