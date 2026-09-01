import json

import pytest

from src.m2_rag.config import RAGConfig
from src.m2_rag.evaluation import RetrievalExample, benchmark_retrieval_latency, recall_at_k
from src.m2_rag.finetuning.prepare import load_annotated_dataset
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
    assert report.runs == 3 and report.backend == "memory-exact" and report.corpus_size == 2
    assert report.environment and report.p50_ms >= 0


def test_m3_hook_is_optional_and_exposes_expected_parameters():
    params = experiment_parameters(RAGConfig(), embedding_dimension=37)
    assert params["embedding_dimension"] == 37
    assert params["retrieval_method"] == "hybrid_rrf"
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
