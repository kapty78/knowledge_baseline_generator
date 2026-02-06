# Wissensbasis-API (Render-ready)

## Schnellstart lokal

```bash
pip install -r requirements.txt
cp .env.example .env
# .env: API_KEY, GEMINI_API_KEY, OPENAI_API_KEY eintragen

uvicorn app:app --host 0.0.0.0 --port 8000
```

## Endpoints

### POST /v1/jobs
Startet Pipeline. Body:
```json
{
  "file_urls": [
    "https://xxx.supabase.co/storage/v1/object/public/bucket/file1.pdf",
    "https://xxx.supabase.co/storage/v1/object/public/bucket/file2.docx"
  ]
}
```

Header: `X-API-Key: <API_KEY>`

Response: `{"job_id": "abc123", "status": "pending"}`

### GET /v1/jobs/{job_id}
Status abfragen.

Response (done): `{"job_id": "abc123", "status": "done", "result_url": "/v1/jobs/abc123/result"}`

### GET /v1/jobs/{job_id}/result
PDF-Download (nur wenn status=done).

## Pipeline lokal testen (ohne API)

```bash
# Mit URLs (Supabase)
python pipeline_universal.py --urls "https://..." "https://..." --output ./out

# Mit lokalen Dateien
python pipeline_universal.py --local datei1.pdf datei2.txt --output ./out
```

## Render deploy

1. Repo mit Render verbinden
2. `render.yaml` nutzen oder manuell:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn app:app --host 0.0.0.0 --port $PORT`
3. Env Vars setzen: API_KEY, GEMINI_API_KEY, OPENAI_API_KEY
