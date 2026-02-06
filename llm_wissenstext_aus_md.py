#!/usr/bin/env python3
"""
Wissenstext aus KI-Wissensextraktion erzeugen

Liest die große MD-Datei (KI_Wissensextraktion_Alle_Mails.md) ein, nutzt
GPT-4.1-mini aus der .env und erzeugt daraus einen kompakten, thematisch
gegliederten Wissenstext für den KI-Support-Agenten.

Ablauf:
  1. MD in Blöcke „## Paar 1“ … „## Paar 141“ zerlegen
  2. Batches von je ~15 Blöcken an die KI: nur Wissenssätze/Regeln extrahieren
  3. Alle Extraktionen sammeln
  4. Ein finaler KI-Aufruf: aus allen Punkten einen dichten, lesbaren
     Wissenstext mit klaren Abschnitten erzeugen (keine Duplikate, keine Beispiele)
  5. Ausgabe: Wissenstext_Support_Agent_LLM.txt

Voraussetzung: .env mit OPENAI_API_KEY und OPENAI_MODEL (z. B. gpt-4.1-mini-2025-04-14).
  Ausführen: .venv/bin/python llm_wissenstext_aus_md.py
"""

import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE = Path(__file__).resolve().parent
INPUT_MD = BASE / "KI_Wissensextraktion_Alle_Mails.md"
OUTPUT_TXT = BASE / "Wissenstext_Support_Agent_LLM.txt"
BATCH_SIZE = 10
PAUSE_SEKUNDEN = 1.0
MAX_RETRIES = 2

# --- MD parsen: Blöcke "## Paar N" bis zum nächsten "## Paar" oder Ende ---


def parse_md_into_blocks(path: Path) -> list[tuple[int, str]]:
    """Liest die MD-Datei und gibt eine Liste (paar_id, block_text) zurück."""
    text = path.read_text(encoding="utf-8")
    # Alle "## Paar N" finden
    pattern = re.compile(r"^## Paar (\d+)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if not matches:
        return []

    blocks = []
    for i, m in enumerate(matches):
        paar_id = int(m.group(1))
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block_text = text[start:end].strip()
        blocks.append((paar_id, block_text))
    return blocks


# --- API: Wissenssätze aus einem Batch von Analysen extrahieren ---


EXTRACT_SYSTEM = """Du bist ein Experte für Wissensextraktion. Deine Aufgabe: Aus Analysen von Kundendienst-E-Mails (USD Reisen) nur allgemeingültige Wissenssätze und Regeln für einen KI-Support-Agenten herausziehen.
Keine Fallbeispiele, keine Einzelfallbeschreibungen, keine Duplikate innerhalb deiner Antwort. Jeder Punkt: eine prägnante, sachliche Aussage auf Deutsch."""

EXTRACT_USER_TEMPLATE = """Es folgen {n} Analysen (jeweils „## Paar …“). Jede enthält: Inhalt, ableitbares Wissen, Verhalten des Support-Agenten, Besonderheiten.

Extrahiere daraus NUR die allgemeingültigen Wissenssätze und Regeln für einen Support-Agenten von USD Reisen. Ausgabe: eine nummerierte Liste von Wissenssätzen (pro Zeile ein Punkt, knapp und faktenorientiert). Keine Einleitung, keine Beispiele.

---
{blocks}
---
Ende der Analysen. Liste der Wissenssätze:"""


def extract_knowledge_batch(client: OpenAI, model: str, blocks: list[tuple[int, str]]) -> str:
    """Sendet einen Batch von Blöcken an die KI, liefert die extrahierten Wissenssätze als Text."""
    combined = "\n\n".join(block_text for _, block_text in blocks)
    n = len(blocks)
    user_msg = EXTRACT_USER_TEMPLATE.format(n=n, blocks=combined)

    for attempt in range(MAX_RETRIES + 1):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": EXTRACT_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.2,
            )
            return (r.choices[0].message.content or "").strip()
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(5)
                continue
            raise RuntimeError(f"API-Fehler nach {MAX_RETRIES + 1} Versuchen: {e}") from e


# --- API: Aus allen Extraktionen den finalen Wissenstext erzeugen ---


MERGE_SYSTEM = """Du bist ein Redakteur für Wissensbasen. Du erstellst aus einer langen Liste von Wissenssätzen einen einzigen, thematisch gegliederten, dichten Wissenstext für einen KI-Support-Agenten. Keine Beispiele, keine Duplikate, klare Abschnitte. Stil: sachlich, prägnant, auf Deutsch."""

MERGE_USER_TEMPLATE = """Es folgen Wissenssätze, die aus 141 Kundendienst-Analysen von USD Reisen (Urlaubs Service Deutschland) extrahiert wurden.

Erstelle daraus EINEN kompakten Wissenstext mit klaren Abschnitten. Orientiere dich an dieser Gliederung (und ergänze bei Bedarf):
1. Unternehmen & Kontakt
2. Gutscheine & Partner
3. Werbung & Datenschutz
4. Stornierung & Rücktritt
5. Reiseunterlagen, Abholzeit, Zustieg
6. Zahlung & Rückerstattung
7. Versicherung & Empfehlungen
8. Sonstiges

Pro Abschnitt: Überschrift (## …), darunter Bullet-Points mit den relevanten Regeln/Fakten. Keine Duplikate, keine Einzelfallbeispiele. Ziel: Eine durchgehend lesbare Wissensbasis für einen RAG-Support-Agenten.

---
{extractions}
---
Ende der Liste. Dein Wissenstext:"""


def build_final_wissenstext(client: OpenAI, model: str, all_extractions: str) -> str:
    """Erzeugt aus der Gesamtliste der Extraktionen den finalen Wissenstext."""
    # Falls zu lang für einen Call, kürzen wir auf die letzten ~100k Zeichen (sollte selten nötig sein)
    max_chars = 90_000
    if len(all_extractions) > max_chars:
        all_extractions = "... [gekürzt] ...\n\n" + all_extractions[-max_chars:]

    user_msg = MERGE_USER_TEMPLATE.format(extractions=all_extractions)

    for attempt in range(MAX_RETRIES + 1):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": MERGE_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.3,
            )
            return (r.choices[0].message.content or "").strip()
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(5)
                continue
            raise RuntimeError(f"API-Fehler (Merge) nach {MAX_RETRIES + 1} Versuchen: {e}") from e


def run_with_paths(input_md: Path, output_txt: Path) -> None:
    """Erzeugt aus KI-Wissensextraktion-MD einen kompakten Wissenstext. input_md → output_txt."""
    api_key = os.environ.get("OPENAI_API_KEY")
    model = (os.environ.get("OPENAI_MODEL") or "gpt-4.1-mini").strip()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY fehlt. Bitte .env setzen.")
    if not input_md.exists():
        raise SystemExit(f"Eingabedatei fehlt: {input_md}")
    client = OpenAI(api_key=api_key)
    print("Lese MD-Datei und zerlege in Blöcke …")
    blocks = parse_md_into_blocks(input_md)
    if not blocks:
        raise SystemExit("Keine „## Paar N“-Blöcke in der MD-Datei gefunden.")
    print(f"  → {len(blocks)} Blöcke (Paar 1 … {blocks[-1][0]})")
    batches = [blocks[i : i + BATCH_SIZE] for i in range(0, len(blocks), BATCH_SIZE)]
    print(f"  → {len(batches)} Batches à max. {BATCH_SIZE} Blöcke")
    all_extractions = []
    for idx, batch in enumerate(batches, 1):
        print(f"  Batch {idx}/{len(batches)} (Paar {batch[0][0]}–{batch[-1][0]}) …")
        text = extract_knowledge_batch(client, model, batch)
        all_extractions.append(f"--- Batch {idx} ---\n{text}")
        time.sleep(PAUSE_SEKUNDEN)
    combined_extractions = "\n\n".join(all_extractions)
    print("Erzeuge finalen Wissenstext …")
    final_text = build_final_wissenstext(client, model, combined_extractions)
    time.sleep(PAUSE_SEKUNDEN)
    output_txt.parent.mkdir(parents=True, exist_ok=True)
    output_txt.write_text(final_text, encoding="utf-8")
    print(f"Fertig. Ausgabe: {output_txt}")


def main() -> None:
    if not INPUT_MD.exists():
        raise SystemExit(f"Eingabedatei fehlt: {INPUT_MD}")
    run_with_paths(INPUT_MD, OUTPUT_TXT)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Wissenstext aus KI-Wissensextraktion-MD erzeugen")
    p.add_argument("--input", type=Path, default=INPUT_MD)
    p.add_argument("--output", type=Path, default=OUTPUT_TXT)
    args = p.parse_args()
    if args.input != INPUT_MD or args.output != OUTPUT_TXT:
        run_with_paths(args.input, args.output)
    else:
        main()
