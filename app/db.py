import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import DATA_DIR, DB_PATH


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(DATA_DIR, 0o700)
    except OSError:
        pass
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 30000")
    return db


def initialize():
    with connect() as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS batches (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            job_description TEXT NOT NULL,
            criteria_json TEXT,
            shortlist_percent INTEGER NOT NULL,
            final_percent INTEGER NOT NULL DEFAULT 10,
            final_count INTEGER NOT NULL,
            status TEXT NOT NULL,
            screening_provider TEXT NOT NULL DEFAULT 'laya',
            total_count INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS candidates (
            id TEXT PRIMARY KEY,
            batch_id TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            storage_path TEXT,
            status TEXT NOT NULL,
            error_code TEXT,
            initial_score REAL,
            match_probability REAL,
            score_confidence REAL,
            mandatory_probability REAL,
            mandatory_pass INTEGER NOT NULL DEFAULT 1,
            stack_match REAL NOT NULL DEFAULT 1,
            equivalent_match REAL NOT NULL DEFAULT 0,
            shortlist_tier TEXT,
            project_score REAL,
            model_name TEXT,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            initial_json TEXT,
            project_urls_json TEXT,
            external_json TEXT,
            final_score REAL,
            final_rank INTEGER,
            is_finalist INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
            candidate_id TEXT REFERENCES candidates(id) ON DELETE CASCADE,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            run_after REAL NOT NULL DEFAULT 0,
            locked_until REAL NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(batch_id, stage, candidate_id)
        );
        CREATE INDEX IF NOT EXISTS task_queue_idx ON tasks(status, run_after, locked_until, id);
        CREATE INDEX IF NOT EXISTS candidate_batch_idx ON candidates(batch_id, initial_score DESC);
        """)
        columns = {row[1] for row in db.execute("PRAGMA table_info(candidates)").fetchall()}
        for name, sql_type in (("match_probability", "REAL"), ("score_confidence", "REAL"),
                               ("model_name", "TEXT"), ("input_tokens", "INTEGER NOT NULL DEFAULT 0"),
                               ("mandatory_probability", "REAL"), ("mandatory_pass", "INTEGER NOT NULL DEFAULT 1"),
                               ("stack_match", "REAL NOT NULL DEFAULT 1"), ("equivalent_match", "REAL NOT NULL DEFAULT 0"),
                               ("shortlist_tier", "TEXT"), ("project_score", "REAL")):
            if name not in columns:
                db.execute(f"ALTER TABLE candidates ADD COLUMN {name} {sql_type}")
        batch_columns = {row[1] for row in db.execute("PRAGMA table_info(batches)").fetchall()}
        if "screening_provider" not in batch_columns:
            db.execute("ALTER TABLE batches ADD COLUMN screening_provider TEXT NOT NULL DEFAULT 'laya'")
        if "final_percent" not in batch_columns:
            db.execute("ALTER TABLE batches ADD COLUMN final_percent INTEGER NOT NULL DEFAULT 10")
        # A retrying task is queued, even if its earlier attempt left the
        # candidate marked as actively screening/checking. Repair that mismatch
        # when either the API or worker starts.
        db.execute("""
            UPDATE candidates
            SET status='queued', error_code=(SELECT last_error FROM tasks WHERE tasks.candidate_id=candidates.id AND stage='screening')
            WHERE id IN (SELECT candidate_id FROM tasks WHERE stage='screening' AND status='queued')
        """)
        db.execute("""
            UPDATE candidates
            SET status='deep_queued', error_code=(SELECT last_error FROM tasks WHERE tasks.candidate_id=candidates.id AND stage='deep')
            WHERE id IN (SELECT candidate_id FROM tasks WHERE stage='deep' AND status='queued')
        """)


def create_batch(batch_id: str, title: str, description: str, shortlist_percent: int,
                 final_percent: int, candidates: list[dict], criteria: list[dict] | None,
                 screening_provider: str = "laya"):
    stamp = now_iso()
    criteria = criteria or []
    valid_count = sum(1 for item in candidates if item.get("status") == "queued")
    status = "screening" if valid_count else "completed"
    with connect() as db:
        db.execute("""
            INSERT INTO batches (id,title,job_description,criteria_json,shortlist_percent,final_percent,final_count,status,total_count,screening_provider,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (batch_id, title, description, json.dumps(criteria) if criteria is not None else None,
              shortlist_percent, final_percent, 0, status, len(candidates), screening_provider, stamp, stamp))
        for item in candidates:
            db.execute("""
                INSERT INTO candidates (id,batch_id,filename,storage_path,status,error_code,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (item["id"], batch_id, item["filename"], item.get("storage_path"), item["status"],
                  item.get("error_code"), stamp, stamp))
            if item.get("status") == "queued":
                db.execute("INSERT INTO tasks (batch_id,candidate_id,stage,status,created_at) VALUES (?,?, 'screening','queued',?)",
                           (batch_id, item["id"], stamp))
    if valid_count:
        finalize_screening_if_ready(batch_id)


def get_batch(batch_id: str):
    with connect() as db:
        row = db.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
    if not row:
        return None
    batch = dict(row)
    batch["criteria"] = json.loads(batch["criteria_json"]) if batch["criteria_json"] else None
    return batch


def batch_summary(batch_id: str):
    with connect() as db:
        batch = db.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
        if not batch:
            return None
        rows = db.execute("SELECT status, COUNT(*) AS n FROM candidates WHERE batch_id=? GROUP BY status", (batch_id,)).fetchall()
        counts = {row["status"]: row["n"] for row in rows}
        task_rows = db.execute("SELECT stage,status,COUNT(*) AS n FROM tasks WHERE batch_id=? GROUP BY stage,status", (batch_id,)).fetchall()
    with connect() as db:
        usage, jev_usage = db.execute("""
            SELECT COALESCE(SUM(input_tokens),0),
                   COALESCE(SUM(CASE WHEN model_name LIKE 'jev-%' THEN input_tokens ELSE 0 END),0)
            FROM candidates WHERE batch_id=?
        """, (batch_id,)).fetchone()
    return {"batch": dict(batch), "counts": counts, "input_tokens": usage,
            "estimated_cost_usd": jev_usage * 0.042 / 1_000_000,
            "tasks": {f"{row['stage']}_{row['status']}": row["n"] for row in task_rows}}


def list_candidates(batch_id: str, page: int = 1, page_size: int = 50):
    offset = (page - 1) * page_size
    with connect() as db:
        total = db.execute("SELECT COUNT(*) FROM candidates WHERE batch_id=?", (batch_id,)).fetchone()[0]
        finalists = db.execute("""
            SELECT * FROM candidates WHERE batch_id=? AND is_finalist=1 ORDER BY final_rank
        """, (batch_id,)).fetchall()
        candidates = db.execute("""
            SELECT * FROM candidates WHERE batch_id=?
            ORDER BY CASE WHEN initial_score IS NULL THEN 1 ELSE 0 END, initial_score DESC, filename COLLATE NOCASE
            LIMIT ? OFFSET ?
        """, (batch_id, page_size, offset)).fetchall()
    def decode(row):
        candidate = dict(row)
        for key in ("initial_json", "external_json", "project_urls_json"):
            raw = candidate.get(key)
            candidate[key.removesuffix("_json")] = json.loads(raw) if raw else []
        return candidate
    return total, [decode(row) for row in candidates], [decode(row) for row in finalists]


def get_candidate(batch_id: str, candidate_id: str):
    with connect() as db:
        row = db.execute("SELECT * FROM candidates WHERE batch_id=? AND id=?", (batch_id, candidate_id)).fetchone()
    if not row:
        return None
    candidate = dict(row)
    for key in ("initial_json", "external_json", "project_urls_json"):
        raw = candidate.get(key)
        candidate[key.removesuffix("_json")] = json.loads(raw) if raw else []
    return candidate


def candidate_navigation(batch_id: str, candidate_id: str):
    with connect() as db:
        rows = db.execute("""
            SELECT id FROM candidates WHERE batch_id=?
            ORDER BY CASE WHEN initial_score IS NULL THEN 1 ELSE 0 END,
                     initial_score DESC, filename COLLATE NOCASE
        """, (batch_id,)).fetchall()
    ids = [row["id"] for row in rows]
    try:
        index = ids.index(candidate_id)
    except ValueError:
        return {"previous": None, "next": None, "position": None, "total": len(ids)}
    return {"previous": ids[index - 1] if index else None,
            "next": ids[index + 1] if index + 1 < len(ids) else None,
            "position": index + 1, "total": len(ids)}


def list_recent_batches(limit: int = 10):
    with connect() as db:
        return [dict(row) for row in db.execute(
            "SELECT id,title,status,total_count,created_at FROM batches ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()]


def claim_task(lease_seconds: int = 300):
    """Claim one queued/expired task atomically, so multiple local workers can share SQLite safely."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""
            SELECT * FROM tasks
            WHERE run_after <= ? AND (status='queued' OR (status='running' AND locked_until < ?))
            ORDER BY CASE stage WHEN 'screening' THEN 0 ELSE 1 END, id
            LIMIT 1
        """, (time.time(), time.time())).fetchone()
        if row is None:
            return None
        task_id = row["id"]
        db.execute("UPDATE tasks SET status='running', attempts=attempts+1, locked_until=? WHERE id=?",
                   (time.time() + lease_seconds, task_id))
        if row["candidate_id"]:
            candidate_status = "screening" if row["stage"] == "screening" else "project_checking"
            db.execute("UPDATE candidates SET status=?,error_code=NULL,updated_at=? WHERE id=?",
                       (candidate_status, now_iso(), row["candidate_id"]))
        updated = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(updated)


def task_context(task: dict):
    with connect() as db:
        batch = db.execute("SELECT * FROM batches WHERE id=?", (task["batch_id"],)).fetchone()
        candidate = db.execute("SELECT * FROM candidates WHERE id=?", (task["candidate_id"],)).fetchone() if task["candidate_id"] else None
    result = {"batch": dict(batch)}
    result["batch"]["criteria"] = json.loads(batch["criteria_json"]) if batch["criteria_json"] else None
    result["candidate"] = dict(candidate) if candidate else None
    if result["candidate"]:
        for key in ("initial_json", "project_urls_json", "external_json"):
            raw = result["candidate"].get(key)
            result["candidate"][key.removesuffix("_json")] = json.loads(raw) if raw else None
    return result


def pending_file_paths(batch_id: str):
    with connect() as db:
        rows = db.execute("SELECT storage_path FROM candidates WHERE batch_id=? AND storage_path IS NOT NULL", (batch_id,)).fetchall()
    return [row["storage_path"] for row in rows]


def save_screening(task: dict, score: float, probability: float, confidence: float,
                   model_name: str, input_tokens: int, findings: dict, project_urls: list[str],
                   mandatory_probability: float, mandatory_pass: bool,
                   stack_match: float, equivalent_match: float):
    context = task_context(task)
    candidate = context["candidate"]
    path = candidate.get("storage_path")
    stamp = now_iso()
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""UPDATE candidates SET status='screened',initial_score=?,match_probability=?,score_confidence=?,
                   mandatory_probability=?,mandatory_pass=?,stack_match=?,equivalent_match=?,model_name=?,input_tokens=?,
                   initial_json=?,project_urls_json=?,storage_path=NULL,updated_at=? WHERE id=?""",
                   (score, probability, confidence, mandatory_probability, int(mandatory_pass), stack_match,
                    equivalent_match, model_name, input_tokens, json.dumps(findings), json.dumps(project_urls),
                    stamp, task["candidate_id"]))
        db.execute("UPDATE tasks SET status='completed',locked_until=0,last_error=NULL WHERE id=?", (task["id"],))
    if path:
        Path(path).unlink(missing_ok=True)
    finalize_screening_if_ready(task["batch_id"])


def save_deep_analysis(task: dict, external: list[dict], final_score: float, project_adjustment: float):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE candidates SET status='deep_completed',external_json=?,final_score=?,project_score=?,updated_at=? WHERE id=?",
                   (json.dumps(external), final_score, project_adjustment, now_iso(), task["candidate_id"]))
        db.execute("UPDATE tasks SET status='completed',locked_until=0,last_error=NULL WHERE id=?", (task["id"],))
    finalize_deep_if_ready(task["batch_id"])


def fail_task(task: dict, error_code: str, retryable: bool, max_attempts: int = 4):
    long_quota_wait = error_code in {"typesafe_rate_limited", "github_rate_limited"}
    can_retry = retryable and task["attempts"] < (100 if long_quota_wait else max_attempts)
    stamp = now_iso()
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if can_retry:
            base_delay = 300 if long_quota_wait else 60
            cap_delay = 3600 if long_quota_wait else 1800
            delay = min(base_delay * (2 ** max(0, task["attempts"] - 1)), cap_delay)
            db.execute("UPDATE tasks SET status='queued',run_after=?,locked_until=0,last_error=? WHERE id=?",
                       (time.time() + delay, error_code, task["id"]))
            if task["candidate_id"]:
                candidate_status = "queued" if task["stage"] == "screening" else "deep_queued"
                db.execute("UPDATE candidates SET status=?,error_code=?,updated_at=? WHERE id=?",
                           (candidate_status, error_code, stamp, task["candidate_id"]))
            return "retry"
        db.execute("UPDATE tasks SET status='failed',locked_until=0,last_error=? WHERE id=?", (error_code, task["id"]))
        if task["stage"] == "screening":
            db.execute("UPDATE candidates SET status='failed',error_code=?,storage_path=NULL,updated_at=? WHERE id=?",
                       (error_code, stamp, task["candidate_id"]))
        else:
            db.execute("UPDATE candidates SET status='deep_failed',error_code=?,final_score=initial_score,updated_at=? WHERE id=?",
                       (error_code, stamp, task["candidate_id"]))
    if task["stage"] == "screening":
        finalize_screening_if_ready(task["batch_id"])
    elif task["stage"] == "deep":
        finalize_deep_if_ready(task["batch_id"])
    return "failed"


def finalize_screening_if_ready(batch_id: str):
    stamp = now_iso()
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        batch = db.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
        if not batch or batch["status"] in ("failed", "completed", "deep_analysis"):
            return
        pending = db.execute("SELECT COUNT(*) FROM tasks WHERE batch_id=? AND stage='screening' AND status IN ('queued','running')", (batch_id,)).fetchone()[0]
        if pending:
            return
        candidates = db.execute("""SELECT id,initial_score,match_probability,mandatory_pass,stack_match,equivalent_match
            FROM candidates WHERE batch_id=? AND status='screened'""", (batch_id,)).fetchall()
        target = min(len(candidates), max(1, (len(candidates) * batch["shortlist_percent"] + 99) // 100)) if candidates else 0
        mandatory_rows = [row for row in candidates if row["mandatory_pass"]]
        exact = [row for row in mandatory_rows if row["stack_match"] >= 0.5]
        exact_ids = {row["id"] for row in exact}
        equivalent = [row for row in mandatory_rows if row["id"] not in exact_ids and row["equivalent_match"] >= 0.5]
        equivalent_ids = {row["id"] for row in equivalent}
        remaining = [row for row in mandatory_rows if row["id"] not in exact_ids and row["id"] not in equivalent_ids]
        ranked = sorted(exact, key=lambda row: (-row["stack_match"], -(row["match_probability"] or 0), -(row["initial_score"] or 0), row["id"]))
        ranked += sorted(equivalent, key=lambda row: (-row["equivalent_match"], -(row["match_probability"] or 0), -(row["initial_score"] or 0), row["id"]))
        ranked += sorted(remaining, key=lambda row: (-(row["match_probability"] or 0), -(row["initial_score"] or 0), row["id"]))
        selected_ids = [row["id"] for row in ranked[:target]]
        final_count = ((len(selected_ids) * batch["final_percent"] + 99) // 100) if selected_ids else 0
        tiers = {row["id"]: ("preferred_stack" if row["id"] in exact_ids
                              else "equivalent_stack" if row["id"] in equivalent_ids
                              else "other_eligible") for row in ranked[:target]}
        db.execute("UPDATE candidates SET status='not_shortlisted',updated_at=? WHERE batch_id=? AND status='screened'", (stamp, batch_id))
        for candidate_id in selected_ids:
            db.execute("UPDATE candidates SET status='deep_queued',shortlist_tier=?,updated_at=? WHERE id=?", (tiers[candidate_id], stamp, candidate_id))
            db.execute("INSERT OR IGNORE INTO tasks (batch_id,candidate_id,stage,status,created_at) VALUES (?,?,'deep','queued',?)",
                       (batch_id, candidate_id, stamp))
        status = "deep_analysis" if selected_ids else "completed"
        db.execute("UPDATE batches SET status=?,final_count=?,updated_at=? WHERE id=?", (status, final_count, stamp, batch_id))
    if selected_ids:
        return


def finalize_deep_if_ready(batch_id: str):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        batch = db.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
        if not batch or batch["status"] != "deep_analysis":
            return
        pending = db.execute("SELECT COUNT(*) FROM tasks WHERE batch_id=? AND stage='deep' AND status IN ('queued','running')", (batch_id,)).fetchone()[0]
        if pending:
            return
        rows = db.execute("""
            SELECT id,final_score,initial_score,match_probability,external_json FROM candidates
            WHERE batch_id=? AND status IN ('deep_completed','deep_failed')
        """, (batch_id,)).fetchall()
        def tie_count(row):
            try:
                return sum(len(source.get("evidence", [])) for source in json.loads(row["external_json"] or "[]"))
            except ValueError:
                return 0
        ordered = sorted(rows, key=lambda row: (-(row["final_score"] if row["final_score"] is not None else row["initial_score"] or 0), -(row["match_probability"] or 0), -tie_count(row), row["id"]))
        finalists = {row["id"] for row in ordered[:batch["final_count"]]}
        stamp = now_iso()
        for rank, row in enumerate(ordered, 1):
            db.execute("UPDATE candidates SET final_rank=?,is_finalist=?,updated_at=? WHERE id=?",
                       (rank, int(row["id"] in finalists), stamp, row["id"]))
        db.execute("UPDATE batches SET status='completed',updated_at=? WHERE id=?", (stamp, batch_id))


def read_batch_criteria(batch_id: str):
    batch = get_batch(batch_id)
    return batch["criteria"] if batch else None


def csv_rows(batch_id: str):
    with connect() as db:
        return db.execute("""
            SELECT filename,status,initial_score,match_probability,score_confidence,mandatory_probability,
                   stack_match,equivalent_match,shortlist_tier,project_score,final_score,final_rank,is_finalist,input_tokens,model_name,error_code
            FROM candidates WHERE batch_id=?
            ORDER BY CASE WHEN final_rank IS NULL THEN 1 ELSE 0 END,final_rank,initial_score DESC,filename
        """, (batch_id,)).fetchall()
