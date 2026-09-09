"""Configuration for M3 experiment tracking."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MLflowConfig:
    """Configuration used by the M3 MLflow adapter."""

    tracking_uri: str = os.getenv("MLFLOW_TRACKING_URI", "mlruns")
    experiment_name: str = os.getenv(
        "MLFLOW_EXPERIMENT_NAME",
        "assistant-juridique-rag",
    )
    registered_model_name: str = os.getenv(
        "MLFLOW_MODEL_NAME",
        "assistant-juridique-rag",
    )
