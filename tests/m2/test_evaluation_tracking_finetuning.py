import json

import pytest

from src.m2_rag.config import RAGConfig
from src.m2_rag.evaluation import RetrievalExample, benchmark_retrieval_latency, recall_at_k
from src.m2_rag.finetuning.prepare import load_annotated_dataset, split_train_validation
from src.m2_rag.finetuning.schema import LoRAConfig
from src.m2_rag.models import RetrievedChunk
from src.m2_rag.tracking import InMemoryTrackingHook, experiment_parameters


def _result(identifier):
    return RetrievedChunk(identifier, identifier, "texte", "titre", "source", "2024",
                          "civil", "fr", 1.0, "dense")


def test_recall_requires_ground_truth_and_computes_only_when_provided():
    with pytest.raises(ValueError, match="ground-truth"):
        recall_at_k([], lambda question, k: [], k=8)
    examples = [RetrievalExample("question", frozenset({"relevant"}))]
    assert recall_at_k(examples, lambda question, k: [_result("relevant")], k=8) == 1.0


def test_latency_report_includes_measurement_context():
    report = benchmark_retrieval_latency(lambda: None, runs=3, backend="memory-exact", corpus_size=2)
    assert report.runs == 3 and report.backend == "memory-exact" and report.chunk_count == 2
    assert report.environment and report.min_ms <= report.mean_ms and report.p50_ms <= report.p95_ms


def test_m3_hook_is_optional_and_exposes_expected_parameters():
    params = experiment_parameters(RAGConfig(), embedding_dimension=37)
    assert params["embedding_dimension"] == 37
    assert params["retrieval_method"] == "hybrid_rrf"
    assert params["chunker_version"] == "legal-v1"
    assert "total_ms" in params["latencies"] and "recall_at_k" in params["available_metrics"]
    hook = InMemoryTrackingHook()
    hook.log_parameters(params)
    assert hook.parameters == [params]


def test_finetuning_contract_is_prepared_but_does_not_train(tmp_path):
    path = tmp_path / "annotated.jsonl"
    path.write_text(json.dumps({
        "question": "Question", "answer": "Réponse", "context": ["Source"],
        "source_doc_ids": ["opaque"], "language": "fr"
    }), encoding="utf-8")
    assert len(load_annotated_dataset(path)) == 1
    assert LoRAConfig(base_model="model").method == "LoRA"
    assert LoRAConfig(base_model="model", quantization_bits=4).method == "QLoRA"


def test_recall_multiple_relevant_ids_zero_results_and_input_validation():
    examples = [RetrievalExample("q", frozenset({"doc-a", "chunk-b"}))]
    assert recall_at_k(examples, lambda question, k: [_result("doc-a")], k=2) == 0.5
    assert recall_at_k(examples, lambda question, k: [], k=2) == 0.0
    with pytest.raises(ValueError):
        RetrievalExample(" ", frozenset({"x"}))
    with pytest.raises(ValueError):
        recall_at_k(examples, lambda question, k: [], k=0)


def test_finetuning_split_and_config_validation(tmp_path):
    examples = [
        {"question": f"Q{i}", "answer": "A", "context": ["C"], "source_doc_ids": [f"d{i}"], "language": "fr"}
        for i in range(4)
    ]
    path = tmp_path / "dataset.jsonl"
    path.write_text("\n".join(json.dumps(item) for item in examples), encoding="utf-8")
    loaded = load_annotated_dataset(path)
    train, validation = split_train_validation(loaded, validation_ratio=0.25, seed=7)
    assert len(train) == 3 and len(validation) == 1
    assert split_train_validation(loaded, validation_ratio=0.25, seed=7)[1] == validation
    with pytest.raises(ValueError):
        LoRAConfig(base_model="model", quantization_bits=3)
