"""MLflow adapter implementing the tracking contract exposed by M2."""

from __future__ import annotations

from typing import Any

from src.m2_rag.models import RAGRequest, RAGResponse

from .config import MLflowConfig


class MLflowTrackingHook:
    """Track M2 RAG experiments and queries with MLflow."""

    def __init__(self, config: MLflowConfig | None = None) -> None:
        try:
            import mlflow
        except ImportError as exc:
            raise RuntimeError(
                "MLflow is required to use MLflowTrackingHook. "
                "Install the M3 tracking dependencies first."
            ) from exc

        self.mlflow = mlflow
        self.config = config or MLflowConfig()

        self.mlflow.set_tracking_uri(self.config.tracking_uri)
        self.mlflow.set_experiment(self.config.experiment_name)

    def log_parameters(self, parameters: dict[str, Any]) -> None:
        """Log experiment configuration parameters."""
        safe_parameters = {
            key: self._serialize_parameter(value)
            for key, value in parameters.items()
        }
        self.mlflow.log_params(safe_parameters)

    def log_metrics(self, metrics: dict[str, float]) -> None:
        """Log numerical evaluation metrics."""
        safe_metrics = {
            key: float(value)
            for key, value in metrics.items()
        }
        self.mlflow.log_metrics(safe_metrics)

    def log_query(
        self,
        request: RAGRequest,
        response: RAGResponse,
    ) -> None:
        """Log observable information for one RAG query."""

        self.mlflow.log_params(
            {
                "prompt_version": response.prompt_version,
                "model_version": response.model_version,
            }
        )

        metrics = {
            key: float(value)
            for key, value in response.latencies.items()
        }

        metrics["retrieved_chunks"] = float(
            len(response.retrieved_chunks)
        )
        metrics["citation_count"] = float(
            len(response.citations)
        )
        metrics["refused"] = float(response.refused)

        self.mlflow.log_metrics(metrics)

        if response.refusal_reason:
            self.mlflow.set_tag(
                "refusal_reason",
                response.refusal_reason,
            )

        self.mlflow.set_tag(
            "query_status",
            "refused" if response.refused else "answered",
        )

    @staticmethod
    def _serialize_parameter(value: Any) -> Any:
        """Convert structured parameters to MLflow-friendly values."""
        if isinstance(value, (list, tuple, set)):
            return ",".join(str(item) for item in value)

        if isinstance(value, dict):
            return ",".join(
                f"{key}={item}"
                for key, item in sorted(value.items())
            )

        return value
