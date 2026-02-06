# Gemini 3 Flash Preview (Google) für universelle Dokumenten-Ingestion

## Idee

Statt für jedes Dateiformat (PDF, DOCX, XLSX, E-Mails, …) eigene Parser zu bauen: **Alle Dokumente als Bilder (PNG) an Gemini 3 Flash Preview schicken**. Das Modell ist stark in Dokumentenverständnis und eignet sich gut, Inhalte für RAG-Systeme aufzubereiten. Unser System muss dazu **alle möglichen Dateien in PNGs umwandeln** können.

## Warum Gemini 3 Flash Preview?

- **Dokumente & RAG**: Für **Vertex AI RAG Engine** und Dokumenten-Workflows ausgelegt. Dateien werden in Überschriften, Absätze, Tabellen und visuelle Elemente segmentiert.
- **Formate**: Akzeptiert **PDF, Bilder (PNG, JPEG, …), Tabellen, Slides** – wir konvertieren alles zu PNG und schicken es durch **Gemini 3 Flash Preview**.
- **Kosten/Performance**: Sehr kostengünstig für Massenkonvertierung von PDFs/Dokumenten für AI.
- **Kontext**: Großer Kontext, viele Seiten pro Request möglich.

## Zwei mögliche Wege

### A) Alles als PNG schicken („ein Trichter für alle Formate“)

- **Jedes** Format (PDF, DOCX, E-Mail-Export, Screenshots, …) wird zuerst in **PNG(s)** umgewandelt (z. B. eine Seite = ein PNG).
- Alle PNGs gehen an **Gemini 3 Flash Preview** mit einem Prompt wie:  
  *„Extrahiere aus diesem Dokument alle Texte und Strukturen für eine Wissensbasis (RAG). Ausgabe: klares Markdown mit Abschnitten, keine Duplikate.“*
- Vorteil: **Ein einziger Eingangskanal** – kein formatabhängiger Code. Layout, Tabellen und Diagramme werden vom Modell interpretiert.
- Nachteil: Konvertierung zu PNG braucht pro Format etwas (PDF → `pdf2image`, DOCX → z. B. über PDF/LibreOffice, E-Mails ggf. als HTML→PNG oder als Text durchreichen).

### B) Native Formate nutzen, wo möglich

- **PDF** und **Bilder** können direkt an die Gemini API übergeben werden (inline oder per File API).
- Wir haben uns für **einheitlich PNG** entschieden: Unser Modul `convert_to_png.py` wandelt **alle** Formate (PDF, DOCX, XLSX, EML, TXT, MD, CSV, HTML, Bilder, …) in PNG(s) um; dann alles durch **Gemini 3 Flash Preview**.
- Vorteil: Weniger Konvertierungsschritte für PDFs/Bilder.  
- Nachteil: Zwei Wege (nativ vs. PNG).

**Empfehlung für „beliebige Dateien reinwerfen“:** Variante A (alles zu PNG) vereinheitlicht die Pipeline und nutzt die Stärke von Gemini im Dokumenten-Vision-Bereich.

## API (Python)

- Paket: `google-generativeai` (neuere Variante: `google-genai` mit `from google import genai`).
- **Inline (kleine Dateien):**  
  `types.Part.from_bytes(data=filepath.read_bytes(), mime_type='application/pdf')` bzw. `image/png` für PNG.
- **Größere Dateien:** File API – `client.files.upload(file="path/to/file.pdf")`, dann `contents=[prompt, uploaded_file]`.
- Modellname z. B. `gemini-2.5-flash` oder `gemini-3-flash-preview` (je nach Verfügbarkeit).

## Einbindung in unsere Pipeline

1. **Upload** (API/Supabase): Beliebig viele Dateien (alle Formate).
2. **Normalisierung**:  
   - Alles in PNG wandeln (PDF → pdf2image, DOCX/ODT → z. B. LibreOffice headless → PDF → PNG, reine Texte optional direkt als Text behalten oder als „Pseudoseite“ in ein PNG packen).
3. **Gemini 3 Flash Preview**:  
   - Pro PNG (oder Batches von PNGs) Aufruf mit Prompt „Extrahiere Text/Struktur für RAG, Ausgabe Markdown“.
   - Ausgaben sammeln → **ein gemeinsames Corpus** (z. B. `## Dokument 1 (dateiname.pdf)\n\n{extrahierter Text}\n\n`).
4. **Weiter wie gehabt**:  
   - Aus diesem Corpus mit GPT (oder wieder Gemini) Wissenssätze extrahieren → kompakter Wissenstext → PDF für die Wissensdatenbank.

Damit ist der „schwierige Trichter“ (beliebige Formate) auf **einen** Schritt reduziert: Format → PNG (via `convert_to_png.py`) → **Gemini 3 Flash Preview** → einheitliches Text-Corpus.

## Quellen (Stand Recherche)

- [Gemini 2.5 Flash – Vertex / Model Card](https://storage.googleapis.com/model-cards/documents/gemini-2.5-flash-preview.pdf)
- [Gemini 2.5 Flash – File Upload and Reading (Document processing, RAG)](https://www.datastudios.org/post/google-gemini-2-5-flash-file-upload-and-reading-document-processing-extraction-quality-multimodal)
- [File input methods – Gemini API](https://ai.google.dev/gemini-api/docs/file-input-methods)
- [Gemini 2.0 Flash – PDF ingestion for RAG](https://gigazine.net/gsc_news/en/20250210-ingesting-pdf-gemini-2-0/)
