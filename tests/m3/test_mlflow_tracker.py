"""Tests for the M3 MLflow tracking adapter."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from src.m3_tracking.config import MLflowConfig
from src.m3_tracking.mlflow_tracker import MLflowTrackingHook


class FakeMLflow:
    """Small MLflow replacement used by unit tests."""

    def __init__(self):
        self.tracking_uri = None
        self.experiment_name = None
        self.params = {}
        self.metrics = {}
        self.tags = {}

    def set_tracking_uri(self, uri):
        self.tracking_uri = uri

    def set_experiment(self, name):
        self.experiment_name = name

    def log_params(self, params):
        self.params.update(params)

    def log_metrics(self, metrics):
        self.metrics.update(metrics)

    def set_tag(self, key, value):
        self.tags[key] = value


def build_tracker(monkeypatch):
    fake_mlflow = FakeMLflow()

    monkeypatch.setitem(
        sys.modules,
        "mlflow",
        fake_mlflow,
    )

    config = MLflowConfig(
        tracking_uri="mlruns-test",
        experiment_name="test-rag-experiment",
        registered_model_name="test-rag-model",
    )

    tracker = MLflowTrackingHook(config)

    return tracker, fake_mlflow


def test_tracker_configures_mlflow(monkeypatch):
    tracker, fake_mlflow = build_tracker(monkeypatch)

    assert tracker.config.experiment_name == "test-rag-experiment"
    assert fake_mlflow.tracking_uri == "mlruns-test"
    assert fake_mlflow.experiment_name == "test-rag-experiment"


def test_log_parameters(monkeypatch):
    tracker, fake_mlflow = build_tracker(monkeypatch)

    tracker.log_parameters(
        {
            "embedding_model": "BAAI/bge-m3",
            "chunk_size": 512,
            "chunk_overlap": 64,
            "available_metrics": [
                "recall_at_k",
                "latency_p95_ms",
            ],
        }
    )

    assert fake_mlflow.params["embedding_model"] == "BAAI/bge-m3"
    assert fake_mlflow.params["chunk_size"] == 512
    assert fake_mlflow.params["chunk_overlap"] == 64

    assert (
        fake_mlflow.params["available_metrics"]
        == "recall_at_k,latency_p95_ms"
    )


def test_log_metrics(monkeypatch):
    tracker, fake_mlflow = build_tracker(monkeypatch)

    tracker.log_metrics(
        {
            "recall_at_8": 0.91,
            "latency_p95_ms": 105.0,
        }
    )

    assert fake_mlflow.metrics["recall_at_8"] == 0.91
    assert fake_mlflow.metrics["latency_p95_ms"] == 105.0


def test_log_query(monkeypatch):
    tracker, fake_mlflow = build_tracker(monkeypatch)

    request = SimpleNamespace(
        question="Quelle est la règle juridique ?"
    )

    response = SimpleNamespace(
        prompt_version="answer_v1",
        model_version="rag-v1",
        latencies={
            "retrieval_ms": 25.0,
            "generation_ms": 80.0,
            "total_ms": 105.0,
        },
        retrieved_chunks=[object(), object(), object()],
        citations=[object(), object()],
        refused=False,
        refusal_reason=None,
    )

    tracker.log_query(request, response)

    assert fake_mlflow.params["prompt_version"] == "answer_v1"
    assert fake_mlflow.params["model_version"] == "rag-v1"

    assert fake_mlflow.metrics["retrieval_ms"] == 25.0
    assert fake_mlflow.metrics["generation_ms"] == 80.0
    assert fake_mlflow.metrics["total_ms"] == 105.0

    assert fake_mlflow.metrics["retrieved_chunks"] == 3.0
    assert fake_mlflow.metrics["citation_count"] == 2.0
    assert fake_mlflow.metrics["refused"] == 0.0

    assert fake_mlflow.tags["query_status"] == "answered"


def test_refused_query_is_tagged(monkeypatch):
    tracker, fake_mlflow = build_tracker(monkeypatch)

    response = SimpleNamespace(
        prompt_version="answer_v1",
        model_version="rag-v1",
        latencies={"total_ms": 12.0},
        retrieved_chunks=[],
        citations=[],
        refused=True,
        refusal_reason="out_of_scope",
    )

    tracker.log_query(object(), response)

    assert fake_mlflow.metrics["refused"] == 1.0
    assert fake_mlflow.tags["query_status"] == "refused"
    assert fake_mlflow.tags["refusal_reason"] == "out_of_scope"
