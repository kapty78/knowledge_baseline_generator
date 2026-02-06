#!/usr/bin/env python3
"""
Echte KI-Wissensextraktion: Geht alle 141 Kundendienst-Paare durch,
ruft für jedes Paar GPT-4.1-mini (OpenAI) auf und lässt die KI ausführlich
analysieren: welche Informationen drinstecken, was sich ableiten lässt,
wie sich der Support-Agent verhalten soll. Ergebnis wird in eine
ausführliche Markdown-Datei geschrieben.

Voraussetzung: .env mit OPENAI_API_KEY (und optional OPENAI_MODEL).
  Beispiel .env:
    OPENAI_API_KEY=sk-...
    OPENAI_MODEL=gpt-4.1-mini
  Ausführen (mit Venv): .venv/bin/python llm_wissensextraktion.py
  Laufzeit: ca. 10–30 Min. (141 API-Calls mit 2 s Pause dazwischen).
"""

import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def bereits_erledigte_ids(datei: Path) -> set[int]:
    """Liest die Ausgabedatei und gibt die IDs der bereits analysierten Paare zurück."""
    if not datei.exists():
        return set()
    text = datei.read_text(encoding="utf-8")
    return set(int(m.group(1)) for m in re.finditer(r"^## Paar (\d+)\s*$", text, re.MULTILINE))

BASE = Path(__file__).resolve().parent
INPUT_JSON = BASE / "paare_141_strukturiert.json"
OUTPUT_MD = BASE / "KI_Wissensextraktion_Alle_Mails.md"
MAX_ANFRAGE_ZEICHEN = 4000
MAX_ANTWORT_ZEICHEN = 3500
PAUSE_SEKUNDEN = 2
MAX_RETRIES = 2

SYSTEM_PROMPT = """Du bist ein Experte für Wissensextraktion aus Kundenservice-E-Mails.
Deine Aufgabe: Aus jedem Paar (Kundenanfrage + Firmenantwort) das zugrundeliegende Wissen,
die Regeln und das erwünschte Verhalten für einen zukünftigen KI-Support-Agenten herausarbeiten.
Antworte ausführlich und strukturiert auf Deutsch. Keine Kurzfassung – lieber zu detailliert als zu knapp."""

USER_PROMPT_TEMPLATE = """Analysiere dieses Kundendienst-E-Mail-Paar des Reiseveranstalters USD Reisen (Urlaubs Service Deutschland).

**Betreff:** {betreff}
**Datum Anfrage:** {datum_eingang}  |  **Datum Antwort:** {datum_antwort}
**Von (Kunde):** {von_kunde}

---
**ANFRAGE (Kunde):**
{anfrage}

---
**ANTWORT (Reiseteam):**
{antwort}

---
Bitte analysiere dieses Paar ausführlich und strukturiert. Beantworte:

1. **Inhalt & Informationen:** Was ist der konkrete Inhalt der Mail? Welche Fakten, Daten oder Umstände werden genannt (z. B. Buchungsnummer, Gutschein, Stornierung, Werbung, Datenschutz)?

2. **Ableitbares Wissen:** Welche allgemeinen Regeln, Richtlinien oder Unternehmenswissen lassen sich daraus ableiten? (z. B. „Werbungssperre wird vorgenommen und dauert ca. vier Wochen“, „Gutscheine kommen von Partnern, nicht von USD“.)

3. **Verhalten des Support-Agenten:** Wie soll ein KI-Support-Agent in einem vergleichbaren Fall reagieren? Was soll er sagen, worauf hinweisen, wohin verweisen? Welche Formulierungen oder Schritte sind typisch?

4. **Besonderheiten / Fallstricke:** Gibt es etwas Spezielles an diesem Fall (z. B. interne Notiz, unvollständige Antwort, Eskalation), das für die Wissensbasis relevant ist?

Schreibe so, dass später ein Redakteur daraus kompakte Wissenssätze für eine Agenten-Wissensbasis formulieren kann. Sei ausführlich."""


def run_with_paths(input_json: Path, output_md: Path) -> int:
    """Führt KI-Wissensextraktion aus: input_json → output_md. Gibt 0 bei Erfolg zurück."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-dein-"):
        print("FEHLER: OPENAI_API_KEY in .env setzen.")
        return 1
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    if not input_json.exists():
        print(f"FEHLER: {input_json} nicht gefunden.")
        return 1
    paare = json.loads(input_json.read_text(encoding="utf-8"))
    paare = sorted(paare, key=lambda p: p["id"])
    total = len(paare)
    client = OpenAI(api_key=api_key)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    erledigt = bereits_erledigte_ids(output_md)
    if erledigt:
        paare = [p for p in paare if p["id"] not in erledigt]
        print(f"Fortsetzung: {len(erledigt)} bereits erledigt, {len(paare)} offen.\n")
    else:
        output_md.write_text(
            "# KI-Wissensextraktion: Kundendienst-Paare\n\n"
            f"Analysiert mit {model}. Pro Paar: Inhalt, abgeleitetes Wissen, "
            "Verhalten des Support-Agenten, Besonderheiten.\n\n---\n\n",
            encoding="utf-8",
        )
    print(f"Ziel: {output_md} | Modell: {model} | Noch: {len(paare)} | Pause: {PAUSE_SEKUNDEN} s\n")
    for i, p in enumerate(paare):
        pid = p["id"]
        betreff = (p.get("betreff") or "").strip() or "(kein Betreff)"
        datum_in = (p.get("datum_eingang") or "").strip()
        datum_out = (p.get("datum_antwort") or "").strip()
        von = (p.get("von_kunde") or "").strip()
        anfrage = (p.get("anfrage_roh") or "").strip()
        antwort = (p.get("antwort_bereinigt") or p.get("antwort_roh") or "").strip()
        if len(anfrage) > MAX_ANFRAGE_ZEICHEN:
            anfrage = anfrage[:MAX_ANFRAGE_ZEICHEN] + "\n\n[... gekürzt ...]"
        if len(antwort) > MAX_ANTWORT_ZEICHEN:
            antwort = antwort[:MAX_ANTWORT_ZEICHEN] + "\n\n[... gekürzt ...]"
        user_text = USER_PROMPT_TEMPLATE.format(
            betreff=betreff, datum_eingang=datum_in, datum_antwort=datum_out,
            von_kunde=von, anfrage=anfrage, antwort=antwort,
        )
        for attempt in range(MAX_RETRIES):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_text},
                    ],
                    temperature=0.3,
                )
                content = (resp.choices[0].message.content or "").strip()
                break
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
                content = f"[FEHLER: {e}]"
                print(f"  Fehler Paar {pid}: {e}")
                break
        block = (
            f"## Paar {pid}\n\n**Betreff:** {betreff}  \n"
            f"**Datum:** {datum_in} → {datum_out}  \n**Von:** {von}\n\n{content}\n\n---\n\n"
        )
        with open(output_md, "a", encoding="utf-8") as f:
            f.write(block)
        print(f"  {i+1}/{len(paare)} Paar {pid} ✓ ({len(erledigt) + i + 1}/{total} gesamt)")
        if i < len(paare) - 1:
            time.sleep(PAUSE_SEKUNDEN)
    print(f"\nFertig. Ausgabe: {output_md}")
    return 0


def main():
    if not INPUT_JSON.exists():
        print(f"FEHLER: {INPUT_JSON} nicht gefunden. Bitte zuerst wissen_analyse_parser.py ausführen.")
        return 1
    return run_with_paths(INPUT_JSON, OUTPUT_MD)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="KI-Wissensextraktion: JSON → Markdown")
    p.add_argument("--input", type=Path, default=INPUT_JSON)
    p.add_argument("--output", type=Path, default=OUTPUT_MD)
    args = p.parse_args()
    if args.input != INPUT_JSON or args.output != OUTPUT_MD:
        raise SystemExit(run_with_paths(args.input, args.output))
    raise SystemExit(main())
