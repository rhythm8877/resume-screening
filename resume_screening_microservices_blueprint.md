# Resume Screening & Candidate Intelligence
## Proposed Microservices Blueprint — Student Project

**Goal:** A manageable portfolio project that supports single-resume job-fit analysis and bulk screening. It should explain evidence behind its results; it must not pretend to predict hiring outcomes.

## 1. Product workflow

### Single-resume mode
A user enters a job description and uploads one PDF/DOCX resume. The system extracts text, compares it with job-specific requirements, and returns a report containing matched criteria, evidence, gaps, uncertainty, and suggestions.

### Batch mode
A recruiter creates a job/rubric and uploads many resumes. Stage 1 screens every readable resume against the same rubric. Stage 2 examines a configurable subset more deeply using relevant public project evidence. The result is a ranked shortlist with a report for each candidate.

Both modes use the **same pipeline**. Single-resume mode is a batch of one.

## 2. Recommended technology stack

| Layer | Recommendation | Why | Alternatives |
|---|---|---|---|
| Frontend | Next.js App Router + TypeScript | Good routing, forms, dashboard and React ecosystem | React + Vite for simpler client-only UI |
| Backend | Python + FastAPI, four separately runnable services | Strong PDF/DOCX and AI/data ecosystem; typed request/response contracts | NestJS/Node.js for one language throughout; Java/Spring Boot if Java is your strongest language |
| Queue/tasks | Celery + Redis with three named queues | Familiar Python worker approach; heavy work runs outside HTTP requests | Celery + RabbitMQ if you specifically want a broker-focused alternative; Kafka is unnecessary here |
| Database | PostgreSQL | Relations, constraints, joins, filtering and analysis history | SQLite for a local-only prototype |
| File storage | Private local storage during development; S3-compatible storage such as MinIO locally or cloud object storage when deployed | Keep binary files separate from relational records | Managed object storage |
| Resume parsing | PDF/DOCX text extraction first | Easy to scope and test; report scanned/empty PDFs rather than inventing content | Add OCR later if scanned resumes matter |
| AI | Provider adapter with structured outputs and configurable models | Makes evaluation/provider changes easier and supports output validation | Rule/embedding baseline or another provider |
| External evidence | GitHub REST API first; limited parsing of explicitly linked project sites | More controlled than scraping entire sites | GitHub GraphQL where it offers a concrete benefit |

Use one queue system, one database deployment and one AI provider integration initially. Verify current AI pricing, rate limits, data handling and quality before choosing a production model. Prefer schema-constrained model outputs, and still validate business rules in application code. See [structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

## 3. Four service boundaries

### Service 1 — Job & Submission API
- Accept a job description, optional editable criteria, and one or many resume files.
- Validate required fields, file size/type/signature and batch count.
- Create a job/batch/analysis ID, save metadata and store files privately.
- Enqueue parsing work and expose status/report endpoints.
- Return quickly; do not perform lengthy parsing or AI calls inside the HTTP request.

### Service 2 — Resume Parsing
- Consume tasks from `resume_parse`.
- Read a file, extract/normalize text, record parser version, and find candidate-provided GitHub/project URLs.
- Store extracted-text artifacts and emit a parsed event/task.
- If a file is corrupt, encrypted, unsupported or text-empty, set a clear failure status. Never fabricate extracted text.

### Service 3 — Preliminary AI Screening
- Consume parsed resumes from `initial_screen`.
- Compare **every resume** against a structured, job-specific rubric.
- Output criterion-level evidence and states such as `supported`, `partial`, `unclear`, and `not_found`, with a provisional score and uncertainty flags.
- Select a configurable subset for deeper analysis while retaining the first-stage result for every resume.
- Bias stage 1 toward recall: avoid discarding plausible candidates too aggressively.

### Service 4 — Deep Evidence & Final Ranking
- Consume shortlisted candidates from `deep_analysis`.
- Inspect relevant public GitHub repositories and explicitly linked project sites, within limits.
- Extract targeted evidence such as repository descriptions, README text, relevant documentation and selected metadata.
- Re-evaluate the role criteria with the additional evidence and save a final evidence-backed report/rank.
- Do not treat commit counts, stars, activity volume or lack of a public profile as direct proof of competence.

### Why these boundaries?
Parsing is file/CPU-oriented; initial screening is AI/provider-rate-limit-oriented; deep research involves external network and rate limits. Separate workers let each stage have its own concurrency and retry settings. They can share a technology stack while being independently runnable/deployable.

## 4. Queue and event flow

Use Celery + Redis initially. Create three named queues:
1. `resume_parse`
2. `initial_screen`
3. `deep_analysis`

Messages should contain identifiers and storage keys—not entire resumes or binary files. A message can include `analysis_id`, `job_id`, `resume_id`, `rubric_version`, `input_storage_key` and `attempt`.

```text
uploaded -> parsing -> parsed -> screening -> shortlisted | not_shortlisted
                                      shortlisted -> deep_analysis -> completed
Any stage can instead end in failed with a safe error code and bounded retry policy.
```

Reliability basics:
- Persist status before/after each stage; PostgreSQL is the status source of truth, not the queue.
- Use task/idempotency keys so retries do not create duplicate reports.
- Retry transient failures only, with a maximum attempt count and backoff.
- Keep a failed-task/dead-letter path for repeated failures.
- Apply per-stage concurrency and provider rate limits.
- One failed resume must not fail the entire batch.

Celery tasks should be idempotent because work may be retried/redelivered; see [Celery task guidance](https://github.com/celery/celery/blob/main/docs/userguide/tasks.rst).

## 5. Data and storage

PostgreSQL metadata/results tables can include:
- `jobs`: title, description, criteria/rubric version, timestamps.
- `batches`: job ID, status, counts and timestamps.
- `resumes`: original filename, private storage key, MIME type, size and parse status.
- `analyses`: job/resume IDs, stage/status, rubric version, score, summary, error code and timestamps.
- `criterion_results`: criterion, state, score, evidence snippet, explanation and source reference.
- `external_evidence`: source type, canonical URL, fetched timestamp, selected text/metadata, relevance and fetch status.

Keep original files and larger extracted-text artifacts in private object storage. PostgreSQL stores their keys and queryable metadata. For a student project, one PostgreSQL instance is enough; use clear service/table ownership and avoid arbitrary cross-service writes. Do not create four separate database servers unless a real requirement emerges.

## 6. Two-stage AI strategy

### Stage 1: broad, cheaper screening
- Parse the job description into a structured rubric once and version it for the entire batch.
- Evaluate every resume against the same criteria.
- Start with a cheaper/faster model or a hybrid of deterministic checks plus AI interpretation.
- Save criterion evidence, gaps and provisional score for every resume.
- Make shortlist size/percentage and minimum thresholds configurable.

### Stage 2: deeper evidence
- Run only for candidates selected by stage 1.
- Fetch relevant GitHub/project-site evidence and tie each finding to a source URL or snippet.
- Ask for structured criterion findings, not an unsupported overall claim.
- Compute the final score in application code using explicit rubric weights and validated criterion values.

**The example 100 → 30 → 10 is a demo configuration, not a universal rule.** The first stage can send about 30 candidates to deeper analysis and the UI can show up to 10 finalists. Users should be able to change those limits. If only six candidates meet the minimum bar, show six; do not pad the shortlist.

**Do not label the output a probability of job success.** A model-generated “82% probability” is not calibrated just because the model emitted a number. Call it a *job-fit/evidence score* unless you later validate probability calibration against a suitable representative outcome dataset. Explain weights, evidence and uncertainty.

## 7. GitHub and project-site evidence

- Prefer the official GitHub API to scraping profile HTML. Use links found in the resume or explicitly supplied by the user.
- Inspect relevant repositories and bounded sources (README, description, relevant documentation). Do not crawl every repo or every commit by default.
- Respect API rate limits and retry according to the returned rate-limit headers. See [GitHub REST API rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api).
- Website fetching needs SSRF protection: validate scheme/host, block localhost/private/link-local addresses, restrict redirects, cap response size, and enforce timeouts. See the [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html).
- A public profile is supplemental evidence, not proof of authorship or job performance. No profile means “no external evidence available,” not a negative score.

## 8. Frontend pages

1. **New analysis:** job description, optional criteria editor, single/bulk upload.
2. **Batch dashboard:** processing counts, per-file status and readable errors.
3. **Initial screening:** provisional score, criterion evidence and shortlist status.
4. **Candidate report:** final score, resume evidence, external source evidence, gaps and uncertainty.
5. **Small settings area:** shortlist size, enrichment toggle and analysis limits.

The frontend should call only Service 1's public API; it should never call worker services directly.

## 9. Single mode and batch mode

Both modes use the same pipeline. Single mode creates one analysis and follows the same status transitions. Batch mode creates one parse task per file; successfully parsed resumes fan out into stage-1 tasks; only shortlisted candidates enter stage 2. Use bounded worker concurrency and per-resume status so a partial failure does not break the batch.

## 10. Build order

1. Create Next.js UI and Service 1 endpoints for jobs, upload metadata and status.
2. Add private file storage and Service 2 PDF/DOCX parsing; finish one-resume extraction.
3. Add Queue 1 and status polling; test corrupt/empty/unsupported files.
4. Add Service 3 and a strict output schema; manually review 5–10 synthetic/consented test resumes.
5. Add configurable top-K/threshold controls and persist stage-1 results for all resumes.
6. Add Service 4, starting with GitHub API evidence; add safe site extraction later.
7. Add retries, idempotency, partial-batch failures, tests and deployment.
8. Test batches of 1, 10 and 100 before making throughput claims.

## 11. Do not add yet

No Kafka, Kubernetes, vector database, complex multi-agent framework, four separate model providers, broad website crawling or separate database servers per service. Add infrastructure only when it solves a demonstrated problem.

## Final recommendation

Use **Next.js + TypeScript**, **four Python/FastAPI services**, **Celery + Redis**, **PostgreSQL**, and **private object storage**. Build and test each queue handoff one at a time. Use one AI provider with a cheaper first-pass configuration and a stronger deep-analysis configuration only if benchmarking supports the cost/quality trade-off. Keep all scores transparent and evidence-based.
