#!/usr/bin/env python3
"""
Schritt 1 der systematischen KI-Analyse: Parst die 141-Paare-Datei,
extrahiert strukturierte Daten und bereinigt die Reiseteam-Antworten
(Entfernung von Zitaten und Signaturblöcken) für die spätere Analyse.
"""

import re
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
INPUT_FILE = BASE / "Wissensbasis_Reiseteam_141_Paare.txt"
OUTPUT_JSON = BASE / "paare_141_strukturiert.json"


def clean_reiseteam_answer(raw: str) -> str:
    """
    Bereinigt den Rohtext der Reiseteam-Antwort:
    - Entfernt zitierte Kundenmail (ab " hat am ... geschrieben:" oder "Ursprüngliche Nachricht")
    - Entfernt Signaturblock am Ende (Tel., Internet, Sitz und Registergericht etc.)
    - Normalisiert Whitespace
    """
    if not raw or not raw.strip():
        return ""

    text = raw.strip()

    # 1) Zitat/Kopie der Kundenmail entfernen: ab " hat am DD.MM.YYYY ... geschrieben:" oder "---------- Ursprüngliche"
    # Pattern: etwas wie "Name <email> hat am 15.03.2025 15:14 CET geschrieben:" oder " hat am ... geschrieben:"
    text = re.sub(
        r"\s+[^\s]+(\s+<[^>]+>)?\s+hat am\s+\d{1,2}\.\d{1,2}\.\d{2,4}[^:]*geschrieben:.*",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(r"\s*----------\s*Ursprüngliche Nachricht\s*----------.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Noch: "Von: ... An: ... Datum: ... Betreff: ..." Blöcke (Forward-Header)
    text = re.sub(r"\s*Von:\s*[^\n]+\s+An:\s*[^\n]+\s+Datum:.*?(?=\n\n|\Z)", "", text, flags=re.DOTALL | re.IGNORECASE)

    # 2) Signaturblock am Ende entfernen (wiederholter Block mit Tel., Internet, Sitz und Registergericht)
    # Typisch: "Beste Grüße, Ihr Reiseteam ... Tel.: 0049 ... Internet: www.usd.reisen ... Sitz und Registergericht ... DE318355174"
    signature_start = re.search(
        r"(Beste Grüße|Mit freundlichen Grüßen|Guten Tag,?)\s*,?\s*(Ihr )?Reiseteam (vom )?Urlaubs Service Deutschland\s*(Tel\.?:|ACHTUNG|Internet:)",
        text,
        flags=re.IGNORECASE,
    )
    if signature_start:
        text = text[: signature_start.start()].strip()

    # Auch: Rest-Signatur wenn oben nicht getroffen (z. B. nur "Tel.: 0049 (0) 4431...")
    if "Sitz und Registergericht Oldenburg HRA 205897" in text:
        idx = text.find("Sitz und Registergericht Oldenburg HRA 205897")
        # Gehe zurück bis zum vorherigen Satzende oder "Tel.:" / "Beste Grüße"
        before = text[:idx]
        last_content = max(
            before.rfind("Beste Grüße"),
            before.rfind("Tel.:"),
            before.rfind("Internet: www"),
        )
        if last_content > 0:
            text = text[:last_content].strip()

    # 3) Mehrfache Leerzeilen und übermäßige Leerzeichen
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    return text.strip()


def parse_paare_file(path: Path) -> list[dict]:
    """Liest die Wissensbasis-Datei und gibt eine Liste von Paar-Dicts zurück."""
    content = path.read_text(encoding="utf-8")

    # Blöcke nach "--- Paar N ---" trennen (ohne Header-Zeilen)
    block_pattern = re.compile(
        r"---\s*Paar\s+(\d+)\s*---\s*\n"
        r"(Betreff:\s*(.+?)\n)?"
        r"(Datum \(Eingang\):\s*(.+?)\n)?"
        r"(.*?Von:\s*(.+?)\n)?"
        r"Datum \(Antwort\):\s*(.+?)\n\n"
        r"\[\s*Anfrage\s*/\s*Kunde\s*\]\s*\n(.*?)\n\[\s*Antwort\s*/\s*Reiseteam\s*\]\s*\n(.*?)"
        r"(?=\n---\s*Paar\s+|\Z)",
        re.DOTALL | re.IGNORECASE,
    )

    # Einfacheres Vorgehen: nach "--- Paar N ---" splitten, dann pro Block regex für Betreff/Datum/Von und die beiden Body-Abschnitte
    blocks = re.split(r"\n---\s*Paar\s+(\d+)\s*---\n", content)[1:]  # [num, text, num, text, ...]
    if len(blocks) % 2 != 0:
        blocks = re.split(r"\n---\s*Paar\s+\d+\s*---\n", content)
        blocks = [b for b in blocks if b.strip() and not b.strip().startswith("WISSENSBASIS") and "Antwort" in b]

    paare = []
    for i in range(0, len(blocks), 2):
        if i + 1 >= len(blocks):
            break
        num_str, block = blocks[i], blocks[i + 1]
        try:
            num = int(num_str)
        except ValueError:
            continue

        # Betreff
        betr = re.search(r"Betreff:\s*(.+?)(?:\n|$)", block, re.IGNORECASE)
        subject = betr.group(1).strip() if betr else ""

        # Datum Eingang
        dat_in = re.search(r"Datum\s*\(Eingang\):\s*([^\n|]+)", block, re.IGNORECASE)
        date_in = dat_in.group(1).strip() if dat_in else ""

        # Von
        von = re.search(r"Von:\s*(.+?)(?:\n|$)", block, re.IGNORECASE)
        from_customer = von.group(1).strip() if von else ""

        # Datum Antwort
        dat_out = re.search(r"Datum\s*\(Antwort\):\s*([^\n]+)", block, re.IGNORECASE)
        date_out = dat_out.group(1).strip() if dat_out else ""

        # [ Anfrage / Kunde ] ... [ Antwort / Reiseteam ]
        anfrage_match = re.search(r"\[\s*Anfrage\s*/\s*Kunde\s*\]\s*\n(.*?)(?=\n\[\s*Antwort\s*/\s*Reiseteam\s*\])", block, re.DOTALL | re.IGNORECASE)
        antwort_match = re.search(r"\[\s*Antwort\s*/\s*Reiseteam\s*\]\s*\n(.*)", block, re.DOTALL | re.IGNORECASE)

        body_customer = anfrage_match.group(1).strip() if anfrage_match else ""
        body_reiseteam_raw = antwort_match.group(1).strip() if antwort_match else ""

        body_reiseteam_clean = clean_reiseteam_answer(body_reiseteam_raw)

        paare.append({
            "id": num,
            "betreff": subject,
            "datum_eingang": date_in,
            "datum_antwort": date_out,
            "von_kunde": from_customer,
            "anfrage_roh": body_customer[:5000],
            "antwort_roh": body_reiseteam_raw[:8000],
            "antwort_bereinigt": body_reiseteam_clean[:6000],
        })
    return paare


def run_with_paths(input_txt: Path, output_json: Path) -> int:
    """Liest paare.txt, schreibt paare_strukturiert.json. Gibt Anzahl Paare zurück."""
    if not input_txt.exists():
        raise FileNotFoundError(f"Datei nicht gefunden: {input_txt}")
    paare = parse_paare_file(input_txt)
    paare.sort(key=lambda x: x["id"])
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(paare, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Parser: {len(paare)} Paare → {output_json}")
    return len(paare)


def main():
    if not INPUT_FILE.exists():
        print(f"Datei nicht gefunden: {INPUT_FILE}")
        return
    paare = parse_paare_file(INPUT_FILE)
    # Sortieren nach ID
    paare.sort(key=lambda x: x["id"])
    OUTPUT_JSON.write_text(json.dumps(paare, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Parsed {len(paare)} Paare → {OUTPUT_JSON}")
    # Kurzstatistik: durchschnittliche Länge Antwort bereinigt
    lens = [len(p["antwort_bereinigt"]) for p in paare]
    print(f"Antwort bereinigt: Ø {sum(lens)//len(lens) if lens else 0} Zeichen, min={min(lens) if lens else 0}, max={max(lens) if lens else 0}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Paare-TXT → strukturiertes JSON")
    p.add_argument("--input", type=Path, default=INPUT_FILE, help="paare.txt")
    p.add_argument("--output", type=Path, default=OUTPUT_JSON, help="paare_strukturiert.json")
    args = p.parse_args()
    if args.input != INPUT_FILE or args.output != OUTPUT_JSON:
        run_with_paths(args.input, args.output)
    else:
        main()
