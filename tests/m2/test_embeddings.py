from src.m2_rag.embeddings import DeterministicFakeEmbedder, SentenceTransformerEmbedder


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
