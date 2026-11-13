import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "screening.db"


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def initialize():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                job_title TEXT NOT NULL,
                filename TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


def save_analysis(analysis_id: str, job_title: str, filename: str, result: dict):
    with connect() as db:
        db.execute(
            "INSERT INTO analyses (id, job_title, filename, result_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (analysis_id, job_title, filename, json.dumps(result), datetime.now(timezone.utc).isoformat()),
        )


def get_analysis(analysis_id: str):
    with connect() as db:
        row = db.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    if not row:
        return None
    result = dict(row)
    result["result"] = json.loads(result.pop("result_json"))
    return result


def recent_analyses(limit: int = 8):
    with connect() as db:
        return db.execute(
            "SELECT id, job_title, filename, created_at FROM analyses ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
