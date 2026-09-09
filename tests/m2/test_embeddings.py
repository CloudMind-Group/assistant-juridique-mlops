from src.m2_rag.embeddings import DeterministicFakeEmbedder, SentenceTransformerEmbedder
from src.m2_rag.generator import TransformersGenerator
from src.m2_rag.models import RetrievedChunk


class TinyModel:
    def get_sentence_embedding_dimension(self):
        return 3

    def encode(self, texts, normalize_embeddings=True):
        return [[float(len(text)), 1.0, 0.0] for text in texts]


def test_fake_embeddings_are_stable_and_configurable():
    embedder = DeterministicFakeEmbedder(dimension=7)
    assert embedder.dimension == 7
    assert embedder.embed_query("droit marocain") == embedder.embed_query("droit marocain")
    assert len(embedder.embed_query("texte")) == 7


def test_dimension_is_derived_from_active_model():
    embedder = SentenceTransformerEmbedder("tiny", model=TinyModel())
    assert embedder.dimension == 3
    assert len(embedder.embed_query("question")) == 3


def test_transformers_generator_adapter_parses_structured_local_output():
    class Pipeline:
        def __call__(self, prompt, **kwargs):
            return [{"generated_text": prompt + '\n{"answer":"Réponse [chunk_id:c]","citation_ids":["c"]}'}]

    chunk = RetrievedChunk("d", "c", "texte", "titre", "source", "2024", "civil", "fr", 1, "dense")
    generated = TransformersGenerator("tiny-smoke-only", pipeline=Pipeline()).generate("Question", [chunk], "v1")
    assert generated.citation_ids == ["c"] and "[chunk_id:c]" in generated.answer
