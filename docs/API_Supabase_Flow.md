# Ablauf: Frontend → Supabase Bucket → Backend per Links

## So funktioniert’s

1. **User** lädt in **deinem Frontend** Dateien hoch (z. B. PDFs, E-Mails, DOCX).
2. Das **Frontend** speichert die Dateien in einem **Supabase Storage Bucket** (nicht beim Backend).
3. Das Frontend ruft **unser Backend** (z. B. auf Render) auf und übergibt nur die **Links** zu diesen Dateien (Supabase-URLs).
4. Das **Backend** lädt die Dokumente von Supabase herunter und verarbeitet sie (PNG-Konvertierung, Gemini, Wissenstext, PDF).

Es werden also **keine** Dateien direkt an das Backend geschickt – nur die URLs. Das Backend holt sich die Dateien selbst von Supabase.

## URLs von Supabase

- **Öffentlicher Bucket:**  
  `https://<project-ref>.supabase.co/storage/v1/object/public/<bucket-name>/<path>/datei.pdf`
- **Privater Bucket (Signed URL):**  
  Nach `createSignedUrl()` erhält das Frontend temporäre URLs, die es an das Backend übergibt. Das Backend kann mit diesen URLs die Dateien herunterladen (ohne eigenen Supabase-Key, die URL enthält schon den Zugriff).

## Backend: Download-Modul

Das Modul **`download_from_urls.py`** macht genau das:

```python
from download_from_urls import download_from_urls

urls = [
    "https://xxx.supabase.co/storage/v1/object/public/documents/kunde1/report.pdf",
    "https://xxx.supabase.co/storage/v1/object/sign/...",  # signed URL
]
ordner, heruntergeladene_dateien = download_from_urls(urls)
# ordner = z. B. /tmp/wissenstext_xyz/
# heruntergeladene_dateien = [ordner / "report.pdf", ...]
```

Danach kann das Backend z. B.:

- alle Dateien in `ordner` mit **`convert_to_png`** in PNGs umwandeln und
- diese PNGs an **Gemini 3 Flash Preview** schicken → Corpus → Wissenstext → PDF.

## API-Annahme (Beispiel)

Der Backend-Service könnte einen Endpoint anbieten:

```json
POST /v1/jobs
{
  "file_urls": [
    "https://xxx.supabase.co/storage/v1/object/public/bucket/doc1.pdf",
    "https://xxx.supabase.co/storage/v1/object/public/bucket/doc2.docx"
  ]
}
```

Backend:

1. Prüft API-Key.
2. Ruft `download_from_urls(file_urls)` auf → temporärer Ordner mit Dateien.
3. Startet Pipeline (PNG → Gemini → Wissenstext → PDF) im Hintergrund.
4. Gibt `job_id` zurück; später `GET /v1/jobs/{job_id}` liefert Status und z. B. Link zum fertigen PDF (wenn das PDF wieder in Supabase hochgeladen wird).

So bleibt die ganze Datei-Logik im Frontend/Supabase; das Backend arbeitet nur mit Links und lädt bei Bedarf von Supabase runter.
