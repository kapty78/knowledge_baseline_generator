#!/usr/bin/env python3
"""
FastAPI-Backend: Wissensbasis-Pipeline als Service (Render-ready).

POST /v1/jobs  { "file_urls": ["https://...supabase.../file.pdf"] }  → job_id
GET  /v1/jobs/{job_id}  → status, result (pdf_url oder download)
GET  /v1/jobs/{job_id}/result  → PDF-Download (wenn done)

Auth: X-API-Key Header (API_KEY in .env)
"""

import os
import tempfile
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, HTTPException, Header
from fastapi.responses import FileResponse

load_dotenv()

from fastapi import FastAPI

app = FastAPI(title="Wissensbasis-Pipeline", version="1.0")

jobs: dict[str, dict] = {}  # job_id -> {status, error?, result_path?}


def _verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    expected = os.environ.get("API_KEY")
    if not expected:
        raise HTTPException(500, "API_KEY nicht konfiguriert")
    if x_api_key != expected:
        raise HTTPException(401, "Ungültiger API-Key")
    return x_api_key


def _run_pipeline(job_id: str, file_urls: list[str]):
    try:
        jobs[job_id]["status"] = "processing"
        out_dir = Path(tempfile.mkdtemp(prefix=f"job_{job_id}_"))
        from pipeline_universal import run_universal_pipeline
        pdf_path = run_universal_pipeline(file_urls, out_dir)
        jobs[job_id]["status"] = "done"
        jobs[job_id]["result_path"] = str(pdf_path)
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)


@app.post("/v1/jobs")
async def create_job(
    body: dict,
    background_tasks: BackgroundTasks,
    _: str = Depends(_verify_api_key),
):
    """Startet Pipeline. Body: { "file_urls": ["url1", "url2", ...] }"""
    urls = body.get("file_urls") or []
    if not urls or not isinstance(urls, list):
        raise HTTPException(400, "file_urls (Liste von URLs) erforderlich")
    job_id = str(uuid.uuid4())[:12]
    jobs[job_id] = {"status": "pending", "file_urls": urls}
    background_tasks.add_task(_run_pipeline, job_id, urls)
    return {"job_id": job_id, "status": "pending"}


@app.get("/v1/jobs/{job_id}")
async def get_job(job_id: str, _: str = Depends(_verify_api_key)):
    """Status und ggf. Ergebnis-Info."""
    if job_id not in jobs:
        raise HTTPException(404, "Job nicht gefunden")
    j = jobs[job_id]
    out = {"job_id": job_id, "status": j["status"]}
    if j.get("error"):
        out["error"] = j["error"]
    if j.get("result_path"):
        out["result_url"] = f"/v1/jobs/{job_id}/result"
    return out


@app.get("/v1/jobs/{job_id}/result")
async def get_job_result(job_id: str, _: str = Depends(_verify_api_key)):
    """PDF-Download (nur wenn status=done)."""
    if job_id not in jobs:
        raise HTTPException(404, "Job nicht gefunden")
    j = jobs[job_id]
    if j["status"] != "done":
        raise HTTPException(409, f"Job noch nicht fertig: {j['status']}")
    path = j.get("result_path")
    if not path or not Path(path).exists():
        raise HTTPException(404, "PDF nicht mehr verfügbar")
    return FileResponse(path, filename="Wissenstext.pdf", media_type="application/pdf")


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
