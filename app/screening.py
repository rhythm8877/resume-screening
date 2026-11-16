"""Select the configured local or hosted stage-one screening provider."""

from app.config import SCREENING_PROVIDER


def evaluate_resume(title: str, job_description: str, resume_text: str, criteria: list[dict]) -> dict:
    if SCREENING_PROVIDER == "laya":
        from app.laya_screening import evaluate_resume as evaluate_with_laya
        return evaluate_with_laya(title, job_description, resume_text, criteria)
    if SCREENING_PROVIDER == "jev":
        from app.jev import evaluate_resume as evaluate_with_jev
        return evaluate_with_jev(title, job_description, resume_text, criteria)
    from app.jev import JevError
    raise JevError("screening_provider_invalid", False)
