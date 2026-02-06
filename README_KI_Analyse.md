# Systematische KI-Analyse der 141 Kundendienst-Paare

Dieses Dokument beschreibt die **reproduzierbare Pipeline** zur Wissensextraktion aus den E-Mail-Paaren (Posteingang + Postausgang) und die Erzeugung des Wissenstexts für den Support-Agenten.

---

## Ablauf (3 Schritte)

### Schritt 1: Parser (`wissen_analyse_parser.py`)

- **Eingabe:** `Wissensbasis_Reiseteam_141_Paare.txt`
- **Aktion:** Zerlegt die Datei in 141 strukturierte Einträge (Betreff, Datum, Von, Anfrage, Antwort). Bereinigt die Reiseteam-Antwort: entfernt zitierte Kundenmails („X hat am … geschrieben:“) und Signaturblöcke (Tel., Internet, Sitz …).
- **Ausgabe:** `paare_141_strukturiert.json` (eine Liste von Objekten pro Paar)

```bash
python3 wissen_analyse_parser.py
```

---

### Schritt 2: KI-Analyse (`wissen_analyse_ki.py`)

- **Eingabe:** `paare_141_strukturiert.json`
- **Aktion:**
  - **Themen-Zuordnung:** Jedes Paar wird anhand von Keywords einem oder mehreren Themen zugeordnet (Gutschein_Partner, Werbung_Datenschutz, Stornierung_Rücktritt, Reiseunterlagen_Abholzeit, Zahlung_Rückerstattung, Versicherung, Kontakt_Öffnungszeiten, Sonstiges).
  - **Satzextraktion:** Aus jeder bereinigten Antwort werden Sätze extrahiert; es werden nur Sätze berücksichtigt, die wissensrelevant wirken (z. B. „Wir sind …“, „Es gilt …“, „Bitte wenden Sie …“).
  - **Häufigkeitsanalyse:** Gleiche oder sehr ähnliche Sätze (nach Normalisierung) werden gezählt → wiederkehrende Aussagen werden sichtbar.
  - **Kandidaten pro Thema:** Pro Thema wird eine sortierte Liste von Satz + Vorkommensanzahl erzeugt.
- **Ausgabe:**
  - `Analyse_Report_KI_Wissen.md` (Themen-Verteilung, Top-Wiederholungen, Kandidaten pro Thema)
  - `Wissens_Kandidaten_pro_Thema.json` (maschinenlesbar für Schritt 3)

```bash
python3 wissen_analyse_ki.py
```

---

### Schritt 3: Wissenstext bauen (`build_wissenstext_aus_analyse.py`)

- **Eingabe:** `Wissens_Kandidaten_pro_Thema.json`
- **Aktion:**
  - Filtert fallbezogene, interne oder Kundenzitate (z. B. „Hallo Angela“, konkrete Buchungsnummern, „Ich fordere …“).
  - Wendet Generalisierungen an (z. B. „Wir haben die Sperrung … vorgenommen“ → „Die Sperrung … wird auf Wunsch vorgenommen“).
  - Dedupliziert über alle Themen (jede Aussage nur einmal).
  - Fügt feste Stammdaten ein (Telefon, Website, Stornierungsadresse buchung@usd.reisen, R+V, etc.).
  - Formatiert den Wissenstext nach Themenblöcken.
- **Ausgabe:** `Wissenstext_Support_Agent_Systematisch.txt`

```bash
python3 build_wissenstext_aus_analyse.py
```

---

## Ausgaben im Überblick

| Datei | Inhalt |
|-------|--------|
| `paare_141_strukturiert.json` | 141 Paare mit bereinigter Antwort (für weitere Analysen) |
| `Analyse_Report_KI_Wissen.md` | Themen-Verteilung, häufigste Aussagen, Kandidaten pro Thema |
| `Wissens_Kandidaten_pro_Thema.json` | Rohe Kandidaten pro Thema (Vorkommen) |
| `Wissenstext_Support_Agent_Systematisch.txt` | Finaler Wissenstext für den KI-Support-Agenten (ohne Beispiele) |

---

## Anpassungen

- **Neue Themen/Keywords:** In `wissen_analyse_ki.py` das Dictionary `THEMEN_KEYWORDS` erweitern.
- **Mehr Generalisierungen:** In `build_wissenstext_aus_analyse.py` das Dictionary `GENERALISIERUNGEN` erweitern.
- **Strengere Filter:** In `build_wissenstext_aus_analyse.py` die Liste `FILTER_PATTERNS` erweitern.
- **Stammdaten:** In `build_wissenstext_aus_analyse.py` die Liste `STAMMDATEN` anpassen.

---

## Vollständiger Lauf

```bash
python3 wissen_analyse_parser.py
python3 wissen_analyse_ki.py
python3 build_wissenstext_aus_analyse.py
```

Der Wissenstext `Wissenstext_Support_Agent_Systematisch.txt` ist die Grundlage für Rack bzw. den Support-Agenten; bei Bedarf kann er redaktionell nachgearbeitet werden.
