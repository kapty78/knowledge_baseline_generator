#!/usr/bin/env python3
"""
Schritt 2 der systematischen KI-Analyse:
- Themen-Zuordnung pro Paar (keyword-basiert)
- Extraktion wissensrelevanter Sätze aus den Reiseteam-Antworten
- Häufigkeitsanalyse: welche Aussagen wiederholen sich
- Ausgabe: Analyse-Report (Markdown) + Kandidaten pro Thema für den Wissenstext
"""

import re
import json
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent
INPUT_JSON = BASE / "paare_141_strukturiert.json"
OUTPUT_REPORT = BASE / "Analyse_Report_KI_Wissen.md"
OUTPUT_KANDIDATEN_JSON = BASE / "Wissens_Kandidaten_pro_Thema.json"

# Themen und zugehörige Keywords (mind. ein Treffer → Paar wird dem Thema zugeordnet)
THEMEN_KEYWORDS = {
    "Gutschein_Partner": [
        "gutschein", "versender", "aussteller", "incentiv", "dankeschön", "partner", "unternehmen nutzen",
        "reiseabwicklung erst ab einlösung", "keinerlei daten", "haben wir nicht", "nicht wir",
        "absender der nachricht", "postadresse des ausstellers", "original vorliegt", "nicht in bar",
    ],
    "Werbung_Datenschutz": [
        "sperrung der daten", "werbung", "angebote", "vier wochen", "umstellung", "newsletter",
        "widerspruch", "löschung", "datenschutz", "dsgvo", "werbeliste", "daten löschen",
    ],
    "Stornierung_Rücktritt": [
        "stornierung", "stornieren", "rücktritt", "reiserücktritt", "stornorechnung", "stornokosten",
        "agb", "reiserecht", "einschreiben", "buchung@usd.reisen", "rechtssicher", "stornobedingungen",
    ],
    "Reiseunterlagen_Abholzeit": [
        "fahrausweis", "voucher", "7-10 tage", "14 tage vor", "abholzeit", "haltestelle",
        "restzahlung", "reiseunterlagen", "detailplanung", "streckenzusammenstellung",
    ],
    "Zahlung_Rückerstattung": [
        "zahlung", "überweisung", "iban", "rückerstattung", "rückzahlung", "verrechnungsscheck",
        "anzahlung", "restzahlung", "lastschrift", "mandat",
    ],
    "Versicherung": [
        "versicherung", "reiserücktritt", "rücktrittskostenversicherung", "travelsecure",
        "reisekranken", "kranken-abbruch",
    ],
    "Kontakt_Öffnungszeiten": [
        "telefon", "04431", "4431 74 89", "öffnungszeiten", "montag", "freitag", "usd.reisen",
        "online-reisebüro", "stationäre", "reisesicherungsschein", "r+v",
    ],
    "Sonstiges_Recht_Adresse": [
        "rechtsanwalt", "briefpost", "adresse", "daten ändern", "umbuchung", "andere person",
    ],
}


def normalize_fuer_vergleich(text: str) -> str:
    """Normalisiert Text für Phrasen-Vergleich (Kleinbuchstaben, Satzzeichen reduziert)."""
    if not text:
        return ""
    t = text.lower().strip()
    t = re.sub(r"[^\wäöüß\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def satz_split(text: str) -> list[str]:
    """Teilt Text in Sätze (einfache Heuristik: . ! ? und Zeilenumbrüche)."""
    if not text or not text.strip():
        return []
    # Zeilenumbrüche als Satzgrenze, dann Punkt/!/?
    text = text.replace("\n", ".\n")
    s = re.split(r"(?<=[.!?])\s+|\n+", text)
    saetze = []
    for x in s:
        x = x.strip()
        if not x or x == ".":
            continue
        x = re.sub(r"^\.+\s*", "", x)
        if len(x) < 15:
            continue
        # Zu kurze oder nur Grußformeln
        if re.match(r"^(Beste Grüße|Mit freundlichen|Guten Tag,?|Moin,?|Hallo,?)\s*$", x, re.I):
            continue
        saetze.append(x)
    return saetze


def themen_zuordnung(paar: dict) -> list[str]:
    """Weist ein Paar anhand von Betreff + Anfrage + Antwort den Themen zu."""
    text = (
        (paar.get("betreff") or "")
        + " "
        + (paar.get("anfrage_roh") or "")[:2000]
        + " "
        + (paar.get("antwort_bereinigt") or "")
        + " "
        + (paar.get("antwort_roh") or "")[:2000]
    ).lower()
    zuordnung = []
    for thema, keywords in THEMEN_KEYWORDS.items():
        if any(kw.lower() in text for kw in keywords):
            zuordnung.append(thema)
    if not zuordnung:
        zuordnung.append("Sonstiges")
    return zuordnung


def ist_wissens_relevant(satz: str) -> bool:
    """Heuristik: Satz klingt nach allgemeiner Regel/Policy (nicht nur fallbezogen)."""
    s = satz.lower()
    # Zu kurz
    if len(s) < 25:
        return False
    # Typische Zitat-/Anrede-Muster (fallbezogen) rausfiltern
    if re.search(r"hat am \d{1,2}\.\d{1,2}\.\d{2,4}", s):
        return False
    if re.search(r"<(?:mailto:)?[^>]+>", s):
        return False
    # Enthält allgemeine Formulierungen (wir sind, sie können, es gilt, bitte beachten, ...)
    policy_muster = [
        r"\bwir sind\b", r"\bwir haben\b", r"\bwir übernehmen\b", r"\bwir empfehlen\b",
        r"\bwir versenden\b", r"\bes gilt\b", r"\blaut\b", r"\bgemäß\b", r"\bvoraussetzung\b",
        r"\bbitte (rufen|senden|wenden|teilen|beachten)\b", r"\bsollten sie\b",
        r"\bder wert (der reise )?kann nicht\b", r"\bdie (reise|stornierung|adresse)\b",
        r"\berst (ab|wenn)\b", r"\bin keiner form\b", r"\bdas sind nicht wir\b",
        r"\bdie (sperrung|umstellung|endgültige)\b", r"\bstornierungen sind\b",
        r"\brechtssicher\b", r"\bagb\b", r"\breiserecht\b", r"\bwww\.usd\.reisen\b",
    ]
    if any(re.search(m, s) for m in policy_muster):
        return True
    # Oder: Satz ist eher lang und enthält keine E-Mail/Name
    if len(s) > 60 and not re.search(r"@|geschrieben|telefon.*\d{5}", s):
        return True
    return False


def main():
    paare = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    # Fallback: wo antwort_bereinigt leer ist, antwort_roh nutzen (gekürzt)
    for p in paare:
        if not (p.get("antwort_bereinigt") or "").strip():
            raw = (p.get("antwort_roh") or "")[:4000]
            p["_text_fuer_analyse"] = raw
        else:
            p["_text_fuer_analyse"] = p.get("antwort_bereinigt") or ""

    # 1) Themen pro Paar
    themen_pro_paar = {}
    themen_haeufigkeit = defaultdict(int)
    for p in paare:
        themen = themen_zuordnung(p)
        themen_pro_paar[p["id"]] = themen
        for t in themen:
            themen_haeufigkeit[t] += 1

    # 2) Sätze extrahieren, normalisieren, zählen (über alle Paare)
    alle_saetze_normalized = defaultdict(list)  # normalized_satz -> [(paar_id, original_satz), ...]
    for p in paare:
        text = p["_text_fuer_analyse"]
        for satz in satz_split(text):
            if not ist_wissens_relevant(satz):
                continue
            norm = normalize_fuer_vergleich(satz)
            if len(norm) < 20:
                continue
            alle_saetze_normalized[norm].append((p["id"], satz))

    # 3) Phrasen gruppieren: sehr ähnliche Sätze zusammenfassen (exakte Normalform = Gruppe)
    # Dann: pro Thema die Sätze sammeln (über themen_pro_paar)
    themen_saetze = defaultdict(list)  # thema -> [(satz, anzahl_paare), ...]
    for norm, vorkommen in alle_saetze_normalized.items():
        if len(vorkommen) < 1:
            continue
        # Repräsentant (längster Original-Satz)
        rep = max(vorkommen, key=lambda x: len(x[1]))[1]
        paar_ids = list({pid for pid, _ in vorkommen})
        for p in paare:
            if p["id"] not in paar_ids:
                continue
            for t in themen_pro_paar[p["id"]]:
                themen_saetze[t].append((rep, len(paar_ids)))

    # Deduplizieren pro Thema: gleicher Satz (normalized) nur einmal, mit max count
    themen_saetze_dedup = {}
    for thema, lst in themen_saetze.items():
        by_norm = {}
        for satz, count in lst:
            norm = normalize_fuer_vergleich(satz)
            if norm not in by_norm or by_norm[norm][1] < count:
                by_norm[norm] = (satz, count)
        themen_saetze_dedup[thema] = sorted(by_norm.values(), key=lambda x: -x[1])

    # 4) Top-Wiederholungen global (für Report)
    wiederholungen = [(norm, len(v)) for norm, v in alle_saetze_normalized.items() if len(v) >= 2]
    wiederholungen.sort(key=lambda x: -x[1])
    top_phrasen = wiederholungen[:80]

    # 5) Report schreiben
    lines = [
        "# KI-Analyse: Wissensextraktion aus 141 Kundendienst-Paaren",
        "",
        "## 1. Themen-Verteilung (Keyword-Zuordnung)",
        "",
        "| Thema | Anzahl Paare |",
        "|-------|--------------|",
    ]
    for thema in sorted(themen_haeufigkeit.keys(), key=lambda t: -themen_haeufigkeit[t]):
        lines.append(f"| {thema} | {themen_haeufigkeit[thema]} |")
    lines.extend([
        "",
        "---",
        "## 2. Häufig wiederkehrende Aussagen (mind. 2-mal vorkommend)",
        "",
    ])
    for norm, count in top_phrasen[:50]:
        # Zeige einen Original-Satz, der zu dieser Normalform gehört
        orig = alle_saetze_normalized[norm][0][1]
        orig_short = orig[:120] + "…" if len(orig) > 120 else orig
        lines.append(f"- **{count}×** {orig_short}")
        lines.append("")
    lines.extend([
        "---",
        "## 3. Wissens-Kandidaten pro Thema (für Wissenstext)",
        "",
    ])
    kandidaten_export = {}
    for thema in sorted(themen_saetze_dedup.keys(), key=lambda t: -len(themen_saetze_dedup[t])):
        kandidaten = themen_saetze_dedup[thema][:35]
        kandidaten_export[thema] = [{"satz": s, "vorkommen": c} for s, c in kandidaten]
        lines.append(f"### {thema}")
        lines.append("")
        for satz, count in kandidaten[:25]:
            lines.append(f"- ({count}×) {satz[:200]}{'…' if len(satz)>200 else ''}")
        lines.append("")

    OUTPUT_REPORT.write_text("\n".join(lines), encoding="utf-8")
    OUTPUT_KANDIDATEN_JSON.write_text(json.dumps(kandidaten_export, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report: {OUTPUT_REPORT}")
    print(f"Kandidaten JSON: {OUTPUT_KANDIDATEN_JSON}")
    print("Themen-Verteilung:", dict(themen_haeufigkeit))


if __name__ == "__main__":
    main()
