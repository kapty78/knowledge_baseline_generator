# Pipeline: E-Mails → Wissenstext-PDF für die Wissensdatenbank

Ein Kunde legt **E-Mails** oder eine **Paare-Datei** ab; die Pipeline erzeugt ein **PDF**, das in die Wissensdatenbank eines KI-Agenten (z. B. RAG) übernommen werden kann.

## Ablauf

1. **E-Mail-Pairing** (wenn Ordner mit Posteingang/Postausgang): Zuordnung Kundenanfrage ↔ Support-Antwort per Message-ID/In-Reply-To → `paare.txt`
2. **Strukturierung**: `paare.txt` → `paare_strukturiert.json` (bereinigte Antworten)
3. **KI-Wissensextraktion**: Pro Paar wird per GPT das Wissen/Verhalten extrahiert → `KI_Wissensextraktion.md`
4. **Kompression**: Aus der großen MD-Datei wird ein kompakter, thematisch gegliederter **Wissenstext** erzeugt → `Wissenstext.txt`
5. **PDF**: Jeder `##`-Abschnitt auf eine eigene Seite → `Wissenstext.pdf`

## Eingabe

### Option A: Zwei E-Mail-Ordner

Lege einen Ordner an mit zwei Unterordnern, die `.eml`-Dateien enthalten:

- **Posteingang**: eingehende Mails (Kundenanfragen)  
  Ordnername muss „posteingang“ oder „Posteingang“ enthalten (z. B. `Posteingang 01.01.25-30.06.25 Reiseteam`).
- **Postausgang**: ausgehende Mails (Support-Antworten)  
  Ordnername muss „postausgang“ oder „Postausgang“ enthalten.

Die Pipeline paart automatisch per **Message-ID** / **In-Reply-To**. Nur Mails aus dem Postausgang, die von der **Support-Domain** stammen (z. B. `@unyflygroup.com`), werden als Antworten gezählt.

### Option B: Fertige Paare-Datei

Wenn du bereits eine Datei im Format „Anfrage + Antwort“ pro Block hast:

- Datei heißt `paare.txt` (oder eine `.txt` mit dem gleichen Aufbau) und liegt im Eingabeordner, **oder**
- Du übergibst direkt die Datei: `--input /pfad/zur/paare.txt`

**Format der Paare-Datei:**

```
--- Paar 1 ---
Betreff: ...
Datum (Eingang): 2025-03-15 15:14 | Von: kunde@example.com
Datum (Antwort): 2025-03-17 12:14

[ Anfrage / Kunde ]
... Text der Kundenmail ...

[ Antwort / Reiseteam ]
... Text der Support-Antwort ...

--- Paar 2 ---
...
```

## Ausführung

```bash
# Mit virtuellem Environment
.venv/bin/python pipeline_wissenstext.py --input /pfad/zum/eingabeordner --output /pfad/zum/ausgabeordner
```

- **`--input`**: Ordner (mit posteingang/postausgang oder paare.txt) oder einzelne Datei `paare.txt`.
- **`--output`**: Ordner für alle Zwischenergebnisse und das finale PDF. Fehlt er, wird `<input>/output` verwendet.
- **`--support-domain`**: E-Mail-Domain des Supports (z. B. `unyflygroup.com`) für das E-Mail-Pairing. Nur Mails von dieser Domain gelten als „Antwort“.

**Beispiel (aktuelles Projekt):**

```bash
.venv/bin/python pipeline_wissenstext.py --input . --output ./output --support-domain unyflygroup.com
```

Dann liegen im Ordner `./output`:

- `paare.txt`
- `paare_strukturiert.json`
- `KI_Wissensextraktion.md`
- `Wissenstext.txt`
- **`Wissenstext.pdf`** ← für die Wissensdatenbank

## Voraussetzungen

- **Python 3.10+** mit Abhängigkeiten aus `requirements.txt` (u. a. `openai`, `python-dotenv`, `reportlab`).
- **.env** mit `OPENAI_API_KEY` und optional `OPENAI_MODEL` (z. B. `gpt-4.1-mini-2025-04-14`) für die KI-Schritte.

## Skalierung pro Kunde

Pro Kunde/Auftrag einen eigenen Ordner anlegen:

```
projekte/
  kunde_xyz/
    posteingang/    # .eml-Dateien
    postausgang/    # .eml-Dateien
  kunde_abc/
    paare.txt       # oder bereits gepaarte Mails
```

Dann z. B.:

```bash
.venv/bin/python pipeline_wissenstext.py -i projekte/kunde_xyz -o projekte/kunde_xyz/output --support-domain kunde-xyz.com
.venv/bin/python pipeline_wissenstext.py -i projekte/kunde_abc -o projekte/kunde_abc/output
```

Das PDF liegt jeweils unter `projekte/<kunde>/output/Wissenstext.pdf` und kann in die Wissensdatenbank des KI-Agenten geladen werden.
