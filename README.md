# Shortlist

**Resume screening and project evidence review for hiring teams.**

Shortlist helps a reviewer compare a group of applications against one job description, focus attention on the most relevant candidates, and inspect evidence from the project links candidates include in their resumes. It keeps the review in one place, from resume upload through a final shortlist and CSV export.

> Shortlist is a decision-support tool. Its scores and checks are signals for human review, not an automated hiring decision.

## What it does

- Creates a screening batch for a role using its title and job description.
- Accepts multiple PDF and DOCX resumes in one upload.
- Extracts resume text and compares it with the role using the selected Stage 1 model.
- Shows fit, essential-requirement, technology-match, confidence, and evidence details in candidate reports.
- Checks the specific project repositories and demo links associated with projects in resumes for candidates advanced to Stage 2.
- Tracks progress, displays the final ranking, and exports batch results to CSV.

## How a screening batch works

1. **Set up the role.** A reviewer enters a job title and pastes the job description, chooses the Stage 1 and final shortlist percentages, and uploads resumes.
2. **Review resumes.** The worker extracts text from each PDF or DOCX and asks the selected Stage 1 provider to compare the resume with the job description. Results include an overall fit estimate, evidence for essential requirements, and technology match estimates.
3. **Choose candidates for project review.** Candidates must meet the model's essential-requirements gate. Among eligible candidates, the app ranks candidates with evidence of the role's named technologies first, candidates with related technology experience next, and other eligible candidates after them. The configured Stage 1 percentage is a cap on the number advanced; it is not a score cutoff. If fewer candidates pass the eligibility gate than there are places, only those candidates advance.
4. **Check linked project evidence.** For candidates who advance, the app checks only project-related GitHub repositories and demo links extracted from their resumes. It reads bounded public material such as repository metadata, README files, dependency manifests, selected source files, and the hosted page's availability and visible page details. LeetCode and similar profile links are not treated as projects.
5. **Review the final shortlist.** Public evidence tied to a project may adjust the Stage 1 score within a limited range. The configured final percentage is applied to the number of candidates who actually reached Stage 2. The reviewer can inspect candidate reports, compare results, and export the batch.

### Understanding the results

- **Fit score** summarizes the model's estimated alignment with the job description. It is not a probability of job success.
- **Essential requirements** indicate whether the model found enough evidence for the role's core requirements. A candidate must pass this gate to be eligible for Stage 2.
- **Technology match** helps order eligible candidates with direct evidence of the technologies named in the job description ahead of candidates whose experience is related or broader.
- **Project evidence** is limited to the resume-linked project sources. A reachable website or matching text can support a claim, but cannot prove authorship or guarantee that every feature works. Missing public evidence is not, by itself, proof that a resume claim is false.
- **Final shortlist** is selected from Stage 2 candidates according to the configured final percentage. The UI presents evidence and status so a person can make the hiring decision.

## Technology

- **Web interface:** Next.js and React
- **API and background processing:** Python, FastAPI, and a separate worker process
- **Resume reading:** `pypdf` for PDFs and `python-docx` for DOCX files
- **Local persistence and task queue:** SQLite
- **Stage 1 screening:** local LAYA model by default, with an optional TypeSafe Jev provider
- **Stage 2 project checks:** bounded public GitHub and website checks; no second AI provider is used

The API and worker run separately so model inference and network checks do not hold open an upload request. SQLite stores batch results and queued work. Uploaded resume files are temporary and are removed after Stage 1 processing; full extracted resume text is not stored in the database.

## Run locally

Requirements: Python 3.10 or newer and Node.js 20.9 or newer.

1. Set up the Python environment from the project root:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   ```

2. Set up the web app:

   ```bash
   cd frontend
   npm install
   cp .env.example .env.local
   ```

3. Start the API, worker, and web app in three terminals. Run the first two commands from the project root and the third from `frontend/`:

   ```bash
   .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   .venv/bin/python -m app.worker
   npm run dev
   ```

4. Open <http://localhost:3000>.

The first local LAYA run may download model files and needs sufficient memory and processing power. Stage 1 uses LAYA by default. To use the optional Jev provider, set `SCREENING_PROVIDER=jev` and add `TYPESAFE_API_KEY` to the root `.env`, then restart the API and worker. An optional `GITHUB_TOKEN` in the root `.env` increases the GitHub API allowance for project checks. Do not commit `.env` or `.env.local` files.

## Project limits

- The current app is designed to run locally and has no user authentication. Keep it bound to localhost; do not expose it publicly as-is.
- It accepts PDF and DOCX files up to 15 MB each, up to 3,000 files per batch, and up to 3 GB total. Processing time depends on local hardware and provider/API limits.
- Scanned PDFs without extractable text may fail processing.
- Stage 2 checks public evidence with bounded requests. It does not run a full browser test suite, prove who authored a repository, or verify every feature of a live project.
- Model outputs can be incomplete or mistaken. Review the resume and linked evidence before making a decision.

## Main project areas

- `frontend/src/app/` — homepage, screening dashboard, batch progress, and candidate reports
- `app/main.py` — upload handling and API endpoints
- `app/worker.py` — resume screening and project-check processing
- `app/resume.py` — PDF/DOCX text extraction and project-link identification
- `app/screening.py` — Stage 1 provider selection and result normalization
- `app/laya_screening.py` and `app/jev.py` — Stage 1 provider integrations
- `app/evidence.py` — GitHub repository and hosted project checks
- `app/db.py` — batch, candidate, and task persistence
