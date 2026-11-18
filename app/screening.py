"""Stage-one provider strategies and their small factory."""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

from app.config import SCREENING_PROVIDER
from app.jev import JevError


@dataclass(frozen=True)
class ScreeningResult:
    """Stable result shape shared by the Stage 1 providers."""

    model: str
    score: float
    score_percent: float
    score_confidence: float
    score_probabilities: dict[str, Any] = field(default_factory=dict)
    meets_minimum_probability: float = 0.0
    review_probability: float = 0.0
    criteria: list[dict[str, Any]] = field(default_factory=list)
    mandatory_probability: float = 0.0
    mandatory_pass: bool = False
    stack_match: float = 0.0
    equivalent_match: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    input_truncated: bool = False

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ScreeningResult":
        """Convert a provider response into the application's stable result type."""
        return cls(
            model=str(payload["model"]),
            score=float(payload["score"]),
            score_percent=float(payload["score_percent"]),
            score_confidence=float(payload["score_confidence"]),
            score_probabilities=payload.get("score_probabilities", {}),
            meets_minimum_probability=float(payload["meets_minimum_probability"]),
            review_probability=float(payload["review_probability"]),
            criteria=payload.get("criteria", []),
            mandatory_probability=float(payload["mandatory_probability"]),
            mandatory_pass=bool(payload["mandatory_pass"]),
            stack_match=float(payload["stack_match"]),
            equivalent_match=float(payload["equivalent_match"]),
            input_tokens=int(payload.get("input_tokens", 0)),
            output_tokens=int(payload.get("output_tokens", 0)),
            input_truncated=bool(payload.get("input_truncated", False)),
        )

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary for persistence and API output."""
        return asdict(self)


class ScreeningProvider(ABC):
    """Strategy interface implemented by every Stage 1 provider."""

    @abstractmethod
    def evaluate(
        self,
        title: str,
        job_description: str,
        resume_text: str,
        criteria: list[dict[str, Any]],
    ) -> ScreeningResult:
        """Compare one resume with a job and return a normalized result."""
        raise NotImplementedError


class LayaScreeningProvider(ScreeningProvider):
    """Adapter for the local LAYA implementation."""

    def evaluate(
        self,
        title: str,
        job_description: str,
        resume_text: str,
        criteria: list[dict[str, Any]],
    ) -> ScreeningResult:
        from app.laya_screening import evaluate_resume

        payload = evaluate_resume(title, job_description, resume_text, criteria)
        return ScreeningResult.from_payload(payload)


class JevScreeningProvider(ScreeningProvider):
    """Adapter for the hosted TypeSafe Jev implementation."""

    def evaluate(
        self,
        title: str,
        job_description: str,
        resume_text: str,
        criteria: list[dict[str, Any]],
    ) -> ScreeningResult:
        from app.jev import evaluate_resume

        payload = evaluate_resume(title, job_description, resume_text, criteria)
        return ScreeningResult.from_payload(payload)


class ProviderFactory:
    """Create the configured Stage 1 strategy in one place."""

    @staticmethod
    def create(provider_name: str | None = None) -> ScreeningProvider:
        name = (provider_name or SCREENING_PROVIDER).strip().lower()
        if name == "laya":
            return LayaScreeningProvider()
        if name == "jev":
            return JevScreeningProvider()
        raise JevError("screening_provider_invalid", False)
