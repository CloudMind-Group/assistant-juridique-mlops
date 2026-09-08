import builtins

import pytest

from src.m2_rag.config import ContextCompressionConfig, QuantizationConfig, RAGConfig
from src.m2_rag.generator import (
    FakeGroundedGenerator, GeneratedAnswer, quantize_torch_cpu,
    transformers_quantization_config,
)
from src.m2_rag.models import RetrievedChunk
from src.m2_rag.service import KeywordScopeGuard, RAGService


def _chunk(identifier="c"):
    return RetrievedChunk(
        f"doc-{identifier}", identifier, f"L'article {identifier} impose une obligation.",
        "Code", "BO", "2024", "civil", "fr", 1.0, "hybrid",
    )


class Retriever:
    def retrieve(self, question, top_k=None, filters=None):
        return [_chunk(question.split()[-1])]


class SequentialGenerator:
    model_version = "sequential"
    def generate(self, question, chunks, prompt_version):
        return GeneratedAnswer(f"Réponse {question} [chunk_id:{chunks[0].chunk_id}]", [chunks[0].chunk_id])


class FailingStreamGenerator(SequentialGenerator):
    def stream(self, question, chunks, prompt_version):
        yield ("start", None)
        raise RuntimeError("generation failed")


def _service(generator=None):
    config = RAGConfig(compression=ContextCompressionConfig(enabled=False))
    return RAGService(
        Retriever(), generator or FakeGroundedGenerator(), config,
        scope_guard=KeywordScopeGuard({"droit"}),
    )


def test_batch_one_and_multiple_preserve_order_and_separate_citations():
    single = _service().query_batch(["droit a"], batch_size=1)
    assert len(single) == 1 and single[0].citations[0].chunk_id == "a"
    responses = _service().query_batch(["droit a", "droit b", "droit c"], batch_size=2)
    assert [item.citations[0].chunk_id for item in responses] == ["a", "b", "c"]


def test_batch_refusal_is_independent_and_fallback_is_sequential():
    service = _service(SequentialGenerator())
    responses = service.query_batch(["droit a", "recette b", "droit c"])
    assert [item.refused for item in responses] == [False, True, False]
    assert [item.citations[0].chunk_id for item in (responses[0], responses[2])] == ["a", "c"]
    with pytest.raises(ValueError, match="batch_size"):
        service.query_batch(["droit a"], batch_size=0)


def test_stream_normal_order_reconstruction_final_citations_and_query_compatibility():
    service = _service()
    events = list(service.stream_query("droit a"))
    assert [event.event for event in events] == ["start", "text_delta", "final", "done"]
    reconstructed = "".join(event.text_delta or "" for event in events)
    final = events[-2].response
    assert final is not None and final.answer.startswith(reconstructed)
    assert [citation.chunk_id for citation in final.citations] == ["a"]
    assert service.query("droit a").citations[0].chunk_id == "a"


def test_stream_refusal_and_generator_error_are_structured():
    refusal = list(_service().stream_query("recette"))
    assert [item.event for item in refusal] == ["start", "refusal", "done"]
    assert refusal[1].response.refused
    failed = list(_service(FailingStreamGenerator()).stream_query("droit a"))
    assert [item.event for item in failed] == ["start", "error", "done"]
    assert "generation failed" in failed[1].error


def test_quantization_modes_validate_and_none_needs_no_optional_runtime(monkeypatch):
    assert transformers_quantization_config(QuantizationConfig("none")) is None
    with pytest.raises(ValueError):
        QuantizationConfig("int2")
    original_import = builtins.__import__
    def blocked_import(name, *args, **kwargs):
        if name == "bitsandbytes":
            raise ImportError("not installed")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", blocked_import)
    with pytest.raises(RuntimeError, match="int8.*bitsandbytes"):
        transformers_quantization_config(QuantizationConfig("int8"))


def test_real_torch_cpu_int8_quantization_on_miniature_model():
    torch = pytest.importorskip("torch")
    model = torch.nn.Sequential(torch.nn.Linear(4, 3), torch.nn.ReLU(), torch.nn.Linear(3, 2))
    quantized = quantize_torch_cpu(model)
    output = quantized(torch.ones(1, 4))
    assert tuple(output.shape) == (1, 2)
    assert "quantized" in type(quantized[0]).__module__
    with pytest.raises(RuntimeError, match="not int4"):
        quantize_torch_cpu(model, "int4")
