import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import DATA_DIR, get_analysis, initialize, recent_analyses, save_analysis
from app.screening import compare_resume, extract_resume_text

ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = DATA_DIR / "uploads"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".docx"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    yield


app = FastAPI(title="Resume Screening", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "error": None,
        "history": recent_analyses(),
        "form": {},
    })


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    job_title: str = Form(...),
    job_description: str = Form(...),
    requirements: str = Form(""),
    resume: UploadFile = File(...),
):
    form = {"job_title": job_title.strip(), "job_description": job_description.strip(), "requirements": requirements.strip()}
    filename = (resume.filename or "resume").replace("\\", "/").split("/")[-1]
    suffix = Path(filename).suffix.lower()
    error = None

    if not form["job_title"]:
        error = "Add a job title."
    elif len(form["job_description"]) < 20:
        error = "Add a job description with at least 20 characters."
    elif suffix not in ALLOWED_SUFFIXES:
        error = "Upload a PDF or DOCX resume."
    elif len(form["requirements"]) > 2000:
        error = "Keep the optional skills list under 2,000 characters."

    stored_path = None
    if error is None:
        content = await resume.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            error = "The resume must be 10 MB or smaller."
        elif suffix == ".pdf" and not content.startswith(b"%PDF-"):
            error = "The selected file does not look like a PDF."
        elif suffix == ".docx" and not content.startswith(b"PK\x03\x04"):
            error = "The selected file does not look like a DOCX document."
        else:
            stored_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
            stored_path.write_bytes(content)
    await resume.close()

    result = None
    if error is None and stored_path:
        try:
            resume_text = extract_resume_text(stored_path)
            result = compare_resume(form["job_description"], resume_text, form["requirements"])
            if not result["requirements"]:
                error = "We could not identify common skills in the job description. Add a few skills in the optional skills field and try again."
            else:
                # The saved report uses excerpts only, not the complete resume text.
                analysis_id = str(uuid.uuid4())
                save_analysis(analysis_id, form["job_title"], filename, result)
                return RedirectResponse(url=f"/analysis/{analysis_id}", status_code=303)
        except ValueError as exc:
            error = str(exc)
        except Exception:
            error = "We could not read this file. Try another PDF or DOCX resume."
        finally:
            stored_path.unlink(missing_ok=True)

    return templates.TemplateResponse(request, "index.html", {
        "error": error,
        "history": recent_analyses(),
        "form": form,
    }, status_code=400)


@app.get("/analysis/{analysis_id}", response_class=HTMLResponse)
def report(request: Request, analysis_id: str):
    analysis = get_analysis(analysis_id)
    if analysis is None:
        return templates.TemplateResponse(request, "not_found.html", status_code=404)
    return templates.TemplateResponse(request, "report.html", {"analysis": analysis, "result": analysis["result"]})
