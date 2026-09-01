from src.m2_rag.chunking import WhitespaceTokenizer, chunk_document
from src.m2_rag.config import ChunkingConfig
from src.m2_rag.models import LegalDocument


def _document(text: str, doc_id: str = "opaque/identifier") -> LegalDocument:
    return LegalDocument(doc_id, "Titre", "Bulletin Officiel", "2024", "Civil", "fr", text)


def test_chunking_respects_512_target_and_64_overlap():
    text = "Article 1\n" + " ".join(f"mot{i}" for i in range(1100))
    chunks = chunk_document(_document(text), ChunkingConfig(512, 64), WhitespaceTokenizer())
    assert len(chunks) == 3
    assert all(chunk.token_count <= 512 for chunk in chunks)
    first = chunks[0].text.split()
    second = chunks[1].text.split()
    assert first[-64:] == second[:64]


def test_chunk_id_is_stable_and_depends_on_version():
    document = _document("Article 1\nUne règle de droit stable.")
    first = chunk_document(document, ChunkingConfig(version="legal-v1"))[0]
    second = chunk_document(document, ChunkingConfig(version="legal-v1"))[0]
    changed = chunk_document(document, ChunkingConfig(version="legal-v2"))[0]
    assert first.chunk_id == second.chunk_id
    assert first.chunk_id != changed.chunk_id
    assert first.doc_id == document.doc_id


def test_detects_french_and_arabic_legal_boundaries():
    text = "Préambule\nArticle 1\nRègle française.\nالمادة 2\nقاعدة قانونية."
    chunks = chunk_document(_document(text), ChunkingConfig(8, 2))
    assert chunks
    assert any(chunk.section and "Article" in chunk.section for chunk in chunks)
    assert any(chunk.section and "المادة" in chunk.section for chunk in chunks)
