import argparse
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

from app.db import claim_task, fail_task, initialize, save_deep_analysis, save_screening, task_context
from app.evidence import inspect_projects, retryable_evidence_error
from app.jev import JevError
from app.resume import extract_job_terms, extract_project_links, extract_resume_text
from app.screening import evaluate_resume


def _project_adjustment(external: list[dict]) -> float:
    # Do not let a generic profile or an unassociated repository affect ranking.
    # Only count evidence where the public source could be tied to a project claim.
    verified_sources = [source for source in external if source.get("project_identity_status") == "confirmed"]
    corroborated = {finding.get("criterion") for source in verified_sources for finding in source.get("evidence", [])}
    verified_technologies = {
        check["technology"]
        for source in verified_sources
        for check in source.get("technology_checks", [])
        if check.get("status") in {"found_in_source_code", "declared_in_dependency_file", "mentioned_in_readme"}
    }
    possible_mismatches = {
        check["technology"]
        for source in verified_sources
        for check in source.get("technology_checks", [])
        if check.get("status") == "possible_mismatch"
    }
    # Public evidence can add points when it corroborates a claim. Missing
    # public evidence is not treated as proof that a resume claim is false.
    bonus = min(10.0, 2.0 * len(corroborated) + len(verified_technologies))
    review_adjustment = min(10.0, 2.0 * len(possible_mismatches))
    return round(bonus - review_adjustment, 1)


def _process(task: dict):
    context = task_context(task)
    batch = context["batch"]
    candidate = context["candidate"]
    try:
        if task["stage"] == "screening":
            path = candidate.get("storage_path")
            if not path or not Path(path).is_file():
                raise ValueError("resume_file_missing")
            resume_text = extract_resume_text(Path(path))
            project_claims = extract_project_links(resume_text)
            project_urls = list(dict.fromkeys(item["url"] for item in project_claims))
            result = evaluate_resume(batch["title"], batch["job_description"], resume_text, batch["criteria"] or [])
            result["project_claims"] = project_claims
            save_screening(
                task, result["score_percent"], result["meets_minimum_probability"],
                result["score_confidence"], result["model"], result["input_tokens"], result, project_urls,
                result["mandatory_probability"], result["mandatory_pass"],
                result["stack_match"], result["equivalent_match"],
            )
            print(f"batch {task['batch_id'][:8]}: {result['model']} screened candidate {candidate['id'][:8]} ({result['score_percent']:.1f})")
            return

        if task["stage"] == "deep":
            evidence_terms = batch["criteria"] or extract_job_terms(batch["job_description"])
            claims = (candidate.get("initial") or {}).get("project_claims", [])
            project_urls = candidate.get("project_urls") or []
            external = inspect_projects(project_urls, evidence_terms, claims)
            adjustment = _project_adjustment(external)
            score = round(max(0.0, min(100.0, (candidate.get("initial_score") or 0) + adjustment)), 1)
            save_deep_analysis(task, external, score, adjustment)
            print(f"batch {task['batch_id'][:8]}: checked {len(project_urls)} resume links into {len(external)} public sources for candidate {candidate['id'][:8]}")
            return
        raise ValueError("unknown_task_stage")
    except JevError as exc:
        retryable = exc.retryable
        error_code = exc.code
    except ValueError as exc:
        retryable = False
        error_code = str(exc) if str(exc) in {"encrypted_pdf", "empty_text", "unsupported_file", "criteria_invalid", "resume_file_missing"} else "resume_processing_failed"
    except Exception as exc:
        if task["stage"] == "deep":
            retryable, error_code = retryable_evidence_error(exc)
        else:
            retryable, error_code = False, "resume_processing_failed"
        print(f"task {task['id']}: {type(exc).__name__} ({error_code})")

    quota_error = error_code in {"typesafe_rate_limited", "laya_model_load_failed"}
    final_attempt = (not retryable) or (task["attempts"] >= (100 if quota_error else 4))
    paths = []
    if task["stage"] == "screening" and final_attempt and candidate.get("storage_path"):
        paths.append(candidate["storage_path"])
    outcome = fail_task(task, error_code, retryable)
    for path in paths:
        Path(path).unlink(missing_ok=True)
    if outcome == "retry":
        print(f"task {task['id']}: retry scheduled ({error_code})")
    else:
        print(f"task {task['id']}: failed ({error_code})")


def _worker_loop(number: int, poll_seconds: float, stop: Event):
    while not stop.is_set():
        task = claim_task()
        if task is None:
            stop.wait(poll_seconds)
            continue
        print(f"worker {number}: {task['stage']} task {task['id']} attempt {task['attempts']}")
        _process(task)


def main():
    parser = argparse.ArgumentParser(description="Process resume screening batches stored in SQLite.")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent local task workers (default: 1; recommended for local model memory)")
    parser.add_argument("--poll-seconds", type=float, default=2)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")
    initialize()
    print(f"Resume screening worker ready ({args.workers} worker(s)). Press Ctrl+C to stop.")
    stop = Event()
    pool = ThreadPoolExecutor(max_workers=args.workers)
    futures = [pool.submit(_worker_loop, number + 1, args.poll_seconds, stop) for number in range(args.workers)]
    try:
        while True:
            time.sleep(0.5)
            for future in futures:
                if future.done():
                    future.result()
    except KeyboardInterrupt:
        print("Stopping worker after current tasks finish.")
    finally:
        stop.set()
        pool.shutdown(wait=True)


if __name__ == "__main__":
    main()
