# Knowledge Baseline Generator

Wissensbasis-Pipeline als Service: Dateien (PDF, DOCX, E-Mails, …) → Wissenstext-PDF für RAG/Wissensdatenbank.

**Flow:** User lädt im Frontend hoch → Supabase Bucket → Backend bekommt Links → Download → PNG → Gemini → Wissenstext → PDF.

## Schnellstart

```bash
pip install -r requirements.txt
cp .env.example .env
# .env: API_KEY, GEMINI_API_KEY, OPENAI_API_KEY

uvicorn app:app --host 0.0.0.0 --port 8000
```

## API

- **POST /v1/jobs** – `{"file_urls": ["https://...supabase.../file.pdf"]}` → job_id
- **GET /v1/jobs/{job_id}** – Status (pending/processing/done/failed)
- **GET /v1/jobs/{job_id}/result** – PDF-Download
- Header: `X-API-Key: <API_KEY>`

Details: [README_API.md](README_API.md)

## Render Deploy

`render.yaml` nutzen oder manuell: Build `pip install -r requirements.txt`, Start `uvicorn app:app --host 0.0.0.0 --port $PORT`. Env: API_KEY, GEMINI_API_KEY, OPENAI_API_KEY.
