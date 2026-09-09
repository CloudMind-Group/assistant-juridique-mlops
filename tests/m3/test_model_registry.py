"""Tests for the M3 Model Registry."""

from types import SimpleNamespace

import pytest

from src.m3_tracking.model_registry import (
    ModelRegistry,
    PromotionPolicy,
)


class FakeRegistryClient:
    def __init__(self):
        self.created_models = []
        self.versions = []
        self.aliases = {}

    def create_registered_model(self, name):
        self.created_models.append(name)

    def create_model_version(self, name, source, run_id):
        self.versions.append(
            {
                "name": name,
                "source": source,
                "run_id": run_id,
            }
        )

        return SimpleNamespace(version="1")

    def set_registered_model_alias(
        self,
        name,
        alias,
        version,
    ):
        self.aliases[(name, alias)] = version


class ExistingModelRegistryClient(FakeRegistryClient):
    """Simulate a lightweight registry where the model already exists."""

    def create_registered_model(self, name):
        raise RuntimeError("registered model already exists")

    def create_model_version(self, name, source, run_id):
        self.versions.append(
            {
                "name": name,
                "source": source,
                "run_id": run_id,
            }
        )

        return SimpleNamespace(version="2")


class BrokenRegistryClient(FakeRegistryClient):
    """Simulate an unexpected registry failure."""

    def create_registered_model(self, name):
        raise RuntimeError("registry unavailable")


def test_register_model_as_candidate():
    client = FakeRegistryClient()

    registry = ModelRegistry(client)

    version = registry.register(
        run_id="run-123",
        source="runs:/run-123/model",
    )

    assert version == "1"

    assert client.aliases[
        ("assistant-juridique-rag", "candidate")
    ] == "1"


def test_register_existing_model_as_candidate_without_mlflow_exception():
    client = ExistingModelRegistryClient()

    registry = ModelRegistry(client)

    version = registry.register(
        run_id="run-456",
        source="runs:/run-456/model",
    )

    assert version == "2"

    assert client.aliases[
        ("assistant-juridique-rag", "candidate")
    ] == "2"

    assert client.versions == [
        {
            "name": "assistant-juridique-rag",
            "source": "runs:/run-456/model",
            "run_id": "run-456",
        }
    ]


def test_register_propagates_unexpected_registry_error():
    client = BrokenRegistryClient()

    registry = ModelRegistry(client)

    with pytest.raises(
        RuntimeError,
        match="registry unavailable",
    ):
        registry.register(
            run_id="run-123",
            source="runs:/run-123/model",
        )


def test_register_rejects_empty_run_id():
    client = FakeRegistryClient()

    registry = ModelRegistry(client)

    with pytest.raises(
        ValueError,
        match="run_id must not be empty",
    ):
        registry.register(
            run_id="",
            source="runs:/run-123/model",
        )


def test_register_rejects_empty_source():
    client = FakeRegistryClient()

    registry = ModelRegistry(client)

    with pytest.raises(
        ValueError,
        match="source must not be empty",
    ):
        registry.register(
            run_id="run-123",
            source="",
        )


def test_model_registry_rejects_empty_model_name():
    client = FakeRegistryClient()

    with pytest.raises(
        ValueError,
        match="model_name must not be empty",
    ):
        ModelRegistry(
            client,
            model_name="   ",
        )


def test_promotion_policy_accepts_valid_metrics():
    policy = PromotionPolicy()

    assert policy.validate(
        {
            "faithfulness": 0.95,
            "hallucination_rate": 0.02,
        }
    )


def test_promotion_policy_rejects_bad_metrics():
    policy = PromotionPolicy()

    assert not policy.validate(
        {
            "faithfulness": 0.90,
            "hallucination_rate": 0.02,
        }
    )

    assert not policy.validate(
        {
            "faithfulness": 0.96,
            "hallucination_rate": 0.05,
        }
    )


def test_promotion_policy_rejects_missing_metrics():
    policy = PromotionPolicy()

    assert not policy.validate(
        {
            "faithfulness": 0.96,
        }
    )

    assert not policy.validate(
        {
            "hallucination_rate": 0.01,
        }
    )


def test_promote_candidate_to_champion():
    client = FakeRegistryClient()

    registry = ModelRegistry(client)

    promoted = registry.promote_to_champion(
        version="3",
        metrics={
            "faithfulness": 0.96,
            "hallucination_rate": 0.01,
        },
    )

    assert promoted is True

    assert client.aliases[
        ("assistant-juridique-rag", "champion")
    ] == "3"


def test_reject_promotion_when_thresholds_fail():
    client = FakeRegistryClient()

    registry = ModelRegistry(client)

    promoted = registry.promote_to_champion(
        version="3",
        metrics={
            "faithfulness": 0.80,
            "hallucination_rate": 0.10,
        },
    )

    assert promoted is False

    assert (
        "assistant-juridique-rag",
        "champion",
    ) not in client.aliases


def test_promote_rejects_empty_version():
    client = FakeRegistryClient()

    registry = ModelRegistry(client)

    with pytest.raises(
        ValueError,
        match="version must not be empty",
    ):
        registry.promote_to_champion(
            version="",
            metrics={
                "faithfulness": 0.96,
                "hallucination_rate": 0.01,
            },
        )
