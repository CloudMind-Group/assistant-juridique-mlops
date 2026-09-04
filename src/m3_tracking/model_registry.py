"""Model Registry utilities for M3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

try:
    from mlflow.exceptions import MlflowException
except ImportError:  # pragma: no cover - handled when registry runtime is used
    MlflowException = None  # type: ignore[assignment,misc]


class RegistryClient(Protocol):
    """Minimal client contract required by M3."""

    def create_registered_model(self, name: str) -> Any:
        ...

    def create_model_version(
        self,
        name: str,
        source: str,
        run_id: str,
    ) -> Any:
        ...

    def set_registered_model_alias(
        self,
        name: str,
        alias: str,
        version: str,
    ) -> None:
        ...


@dataclass(frozen=True)
class PromotionPolicy:
    """Quality thresholds required before model promotion."""

    min_faithfulness: float = 0.94
    max_hallucination_rate: float = 0.03

    def validate(self, metrics: dict[str, float]) -> bool:
        """Return True only when all required quality metrics pass."""

        faithfulness = metrics.get("faithfulness")
        hallucination_rate = metrics.get("hallucination_rate")

        if faithfulness is None or hallucination_rate is None:
            return False

        return (
            faithfulness >= self.min_faithfulness
            and hallucination_rate <= self.max_hallucination_rate
        )


class ModelRegistry:
    """Register and promote RAG/model versions."""

    def __init__(
        self,
        client: RegistryClient,
        model_name: str = "assistant-juridique-rag",
    ) -> None:
        if not model_name.strip():
            raise ValueError("model_name must not be empty")

        self.client = client
        self.model_name = model_name.strip()

    def _ensure_registered_model(self) -> None:
        """Create the registered model unless it already exists.

        MLflow reports an existing model through an MlflowException with
        RESOURCE_ALREADY_EXISTS. Other registry errors must propagate.
        """

        try:
            self.client.create_registered_model(self.model_name)

        except Exception as exc:
            # Do not silently swallow arbitrary failures.
            # Only the MLflow "already exists" condition is accepted.
            if MlflowException is None or not isinstance(exc, MlflowException):
                raise

            error_code = getattr(exc, "error_code", None)

            if error_code != "RESOURCE_ALREADY_EXISTS":
                raise

    def register(
        self,
        *,
        run_id: str,
        source: str,
    ) -> str:
        """Register a new candidate version."""

        if not run_id.strip():
            raise ValueError("run_id must not be empty")

        if not source.strip():
            raise ValueError("source must not be empty")

        self._ensure_registered_model()

        version = self.client.create_model_version(
            name=self.model_name,
            source=source.strip(),
            run_id=run_id.strip(),
        )

        version_number = str(version.version)

        self.client.set_registered_model_alias(
            self.model_name,
            "candidate",
            version_number,
        )

        return version_number

    def promote_to_champion(
        self,
        *,
        version: str,
        metrics: dict[str, float],
        policy: PromotionPolicy | None = None,
    ) -> bool:
        """Promote a candidate only if quality thresholds pass."""

        if not str(version).strip():
            raise ValueError("version must not be empty")

        selected_policy = policy or PromotionPolicy()

        if not selected_policy.validate(metrics):
            return False

        self.client.set_registered_model_alias(
            self.model_name,
            "champion",
            str(version).strip(),
        )

        return True
