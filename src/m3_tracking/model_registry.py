"""Model Registry utilities for M3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


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
        self.client = client
        self.model_name = model_name

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

        try:
            self.client.create_registered_model(self.model_name)
        except Exception as exc:
            # The model may already exist in the registry.
            if "already exists" not in str(exc).lower():
                raise

        version = self.client.create_model_version(
            name=self.model_name,
            source=source,
            run_id=run_id,
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

        selected_policy = policy or PromotionPolicy()

        if not selected_policy.validate(metrics):
            return False

        self.client.set_registered_model_alias(
            self.model_name,
            "champion",
            str(version),
        )

        return True
