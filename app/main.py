import csv
import io
import importlib.util
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import MAX_BATCH_BYTES, MAX_BATCH_FILES, MAX_FILE_BYTES, SCREENING_PROVIDER, TYPESAFE_API_KEY, UPLOAD_DIR
from app.db import (candidate_navigation, create_batch, get_batch, get_candidate, initialize, list_candidates,
                    list_recent_batches)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    yield


app = FastAPI(title="Resume Screening", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
@app.get("/")
def api_root():
    return {"service": "resume-screening-api", "docs": "/docs"}


@app.get("/api/config")
def api_config():
    provider_ready = SCREENING_PROVIDER == "jev" and bool(TYPESAFE_API_KEY)
    if SCREENING_PROVIDER == "laya":
        provider_ready = importlib.util.find_spec("laya") is not None
    return {"provider": SCREENING_PROVIDER, "provider_ready": provider_ready,
            "limits": {"files": MAX_BATCH_FILES, "file_mb": 15, "batch_gb": 3}}


async def _create_batch(
    title: str = Form(...),
    job_description: str = Form(...),
    shortlist_percent: int = Form(30),
    final_percent: int = Form(10),
    consent: bool = Form(False),
    resumes: list[UploadFile] = File(...),
):
    title = title.strip()
    job_description = job_description.strip()
    if SCREENING_PROVIDER not in {"laya", "jev"}:
        raise HTTPException(400, "Set SCREENING_PROVIDER to laya or jev in your local .env file.")
    if SCREENING_PROVIDER == "jev" and not TYPESAFE_API_KEY:
        raise HTTPException(400, "Add TYPESAFE_API_KEY to your local .env file before submitting resumes.")
    if SCREENING_PROVIDER == "laya" and importlib.util.find_spec("laya") is None:
        raise HTTPException(400, "Install project dependencies with pip install -r requirements.txt to use local LAYA.")
    if not title or len(title) > 200:
        raise HTTPException(400, "Enter a job title (up to 200 characters).")
    if len(job_description) < 30 or len(job_description) > 30_000:
        raise HTTPException(400, "The job description must be between 30 and 30,000 characters.")
    if not 1 <= shortlist_percent <= 100:
        raise HTTPException(400, "The first-stage shortlist percentage must be between 1 and 100.")
    if not 1 <= final_percent <= 100:
        raise HTTPException(400, "The final shortlist percentage must be between 1 and 100.")
    if len(resumes) > MAX_BATCH_FILES:
        raise HTTPException(400, f"A batch can contain up to {MAX_BATCH_FILES} resumes.")
    if not resumes:
        raise HTTPException(400, "Choose at least one resume.")
    if not consent:
        raise HTTPException(400, "Confirm that you have permission to process these resumes with the selected screening provider.")
    # Criteria are inferred from the job description by the screening model.
    criteria = []

    batch_id = str(uuid.uuid4())
    batch_dir = UPLOAD_DIR / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    candidates = []
    total_bytes = 0

    for upload in resumes:
        candidate_id = str(uuid.uuid4())
        filename = (upload.filename or "resume").replace("\\", "/").split("/")[-1][:255]
        suffix = Path(filename).suffix.lower()
        candidate = {"id": candidate_id, "filename": filename, "storage_path": None,
                     "status": "queued", "error_code": None}
        if suffix not in {".pdf", ".docx"}:
            candidate.update(status="failed", error_code="unsupported_file_type")
            candidates.append(candidate)
            await upload.close()
            continue

        header = await upload.read(8)
        valid_signature = header.startswith(b"%PDF-") if suffix == ".pdf" else header.startswith(b"PK\x03\x04")
        if not valid_signature:
            candidate.update(status="failed", error_code="file_signature_mismatch")
            candidates.append(candidate)
            await upload.close()
            continue

        storage_path = batch_dir / f"{candidate_id}{suffix}"
        size = len(header)
        if total_bytes + size > MAX_BATCH_BYTES:
            candidate.update(status="failed", error_code="batch_storage_limit")
            candidates.append(candidate)
            await upload.close()
            continue
        try:
            with storage_path.open("xb") as output:
                output.write(header)
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_FILE_BYTES or total_bytes + size > MAX_BATCH_BYTES:
                        raise OverflowError
                    output.write(chunk)
            total_bytes += size
            candidate["storage_path"] = str(storage_path)
        except OverflowError:
            storage_path.unlink(missing_ok=True)
            candidate.update(status="failed", error_code="file_or_batch_too_large")
        except OSError:
            storage_path.unlink(missing_ok=True)
            candidate.update(status="failed", error_code="upload_failed")
        finally:
            await upload.close()
        candidates.append(candidate)

    create_batch(batch_id, title, job_description, shortlist_percent, final_percent, candidates, criteria, SCREENING_PROVIDER)
    return batch_id


@app.post("/api/batches")
async def create_batch_api(
    title: str = Form(...),
    job_description: str = Form(...),
    shortlist_percent: int = Form(30),
    final_percent: int = Form(10),
    consent: bool = Form(False),
    resumes: list[UploadFile] = File(...),
):
    batch_id = await _create_batch(
        title, job_description, shortlist_percent,
        final_percent, consent, resumes,
    )
    return {"batch_id": batch_id, "status": "screening"}


@app.get("/api/batches")
def api_batches():
    return {"batches": list_recent_batches(limit=50)}


@app.get("/api/batches/{batch_id}")
def api_batch(batch_id: str, page: int = 1):
    batch = get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    from app.db import batch_summary
    summary = batch_summary(batch_id)
    total, candidates, finalists = list_candidates(batch_id, max(1, page), page_size=100)
    return {
        "batch": batch,
        "counts": summary["counts"],
        "tasks": summary["tasks"],
        "input_tokens": summary["input_tokens"],
        "estimated_cost_usd": summary["estimated_cost_usd"],
        "candidates": candidates,
        "finalists": finalists,
        "total": total,
        "page": max(1, page),
        "page_size": 100,
    }


@app.get("/api/batches/{batch_id}/candidates/{candidate_id}")
def api_candidate(batch_id: str, candidate_id: str):
    batch = get_batch(batch_id)
    candidate = get_candidate(batch_id, candidate_id)
    if not batch or not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"batch": batch, "candidate": candidate,
            "navigation": candidate_navigation(batch_id, candidate_id)}


@app.get("/api/batches/{batch_id}/export.csv")
def export_batch(batch_id: str):
    batch = get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    from app.db import csv_rows
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["filename", "status", "fit_score", "meets_minimum_probability", "answer_confidence",
                     "mandatory_probability", "preferred_stack_match", "equivalent_stack_match", "shortlist_path",
                     "project_evidence_adjustment", "final_review_points", "final_rank", "finalist", "input_tokens", "model", "error_code"])
    for row in csv_rows(batch_id):
        filename = row["filename"]
        if filename.startswith(("=", "+", "-", "@")):
            filename = "'" + filename
        writer.writerow([filename, row["status"], row["initial_score"], row["match_probability"],
                         row["score_confidence"], row["mandatory_probability"], row["stack_match"],
                         row["equivalent_match"], row["shortlist_tier"], row["project_score"], row["final_score"], row["final_rank"],
                         bool(row["is_finalist"]), row["input_tokens"], row["model_name"], row["error_code"] or ""])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                              headers={"Content-Disposition": f"attachment; filename=resume-screening-{batch_id[:8]}.csv"})
