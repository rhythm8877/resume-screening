# AI Coding Tool Prompt — Resume Screening Microservices Project

Read `resume_screening_microservices_blueprint.md` first. This is a student portfolio and LLD project: keep it practical, demonstrable and explainable, not enterprise-sized.

## Architecture
- Frontend: Next.js App Router + TypeScript.
- Four separately runnable Python/FastAPI services: (1) Job & Submission API, (2) Resume Parsing, (3) Preliminary AI Screening, (4) Deep Evidence & Final Ranking.
- Celery + Redis with queues `resume_parse`, `initial_screen`, `deep_analysis`.
- PostgreSQL for metadata/status/results; private local/object storage for original files and large text artifacts.
- Frontend talks only to the Job & Submission API. Workers communicate through messages containing IDs/storage keys, not entire files.
- Keep model/provider behind an adapter and validate structured output.

## Workflow
Support one resume first, then bulk mode through the same pipeline. Parse the file, evaluate every resume against a structured job rubric, send a configurable top-K subset to deep research, inspect relevant GitHub/project evidence, and save final reports. Persist status and failure details at every stage, and retain stage-1 results for every candidate.

## Guardrails
- Do not call a generated fit score a probability of employment success.
- Never invent extracted text or project evidence.
- Missing evidence is `unclear/not_found`, not proof the candidate lacks a skill.
- No public GitHub profile must not reduce a candidate's score.
- Prefer GitHub API. Fetch only explicit/candidate-provided project URLs and apply SSRF protections, size limits, timeouts and rate limits.
- Do not add Kafka, Kubernetes, vector databases, event buses or extra services without a concrete reason.
- Use one PostgreSQL deployment initially with clear data ownership.
- Do not log full resumes or secrets. Never claim tests passed unless actually run.

## Working method
1. Inspect the repository before editing; never assume it is blank or overwrite working files.
2. Summarize the current state, architecture/modules, first milestone and acceptance criteria.
3. Implement one vertical slice at a time, starting with one PDF/DOCX and one job description.
4. After every milestone, list changed files, commands, tests actually executed, known limitations and next step.
5. Provide `.env.example`, local dependency setup (Docker Compose if useful), API docs and only synthetic/consented test data.
6. Keep README and architecture/data-flow diagrams synchronized with the implementation.

## First response
Inspect the existing repository and the blueprint. Return a concise MVP summary, proposed repo structure, first milestone, acceptance criteria and genuine blockers. Do not dump the whole application at once.
