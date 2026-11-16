import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "screening.db"
TYPESAFE_API_KEY = os.getenv("TYPESAFE_API_KEY", "").strip()
JEV_MODEL = os.getenv("JEV_MODEL", "jev-latest").strip()
SCREENING_PROVIDER = os.getenv("SCREENING_PROVIDER", "laya").strip().lower()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_BATCH_FILES = 3000
MAX_BATCH_BYTES = 3 * 1024 * 1024 * 1024
MAX_RESUME_TEXT = 100_000
