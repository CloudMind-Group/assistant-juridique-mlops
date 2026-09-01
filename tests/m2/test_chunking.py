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


def test_long_french_legal_document_preserves_boundaries_and_splits_large_section():
    articles = [f"Article {i}\n" + " ".join(f"regle{i}_{j}" for j in range(180)) for i in range(1, 5)]
    document = _document("\n".join(articles), "long-fr")
    chunks = chunk_document(document, ChunkingConfig(512, 64), WhitespaceTokenizer())
    assert len(chunks) >= 2
    assert all(chunk.text and 0 < chunk.token_count <= 512 for chunk in chunks)
    assert chunks[0].section == "Article 1"
    assert chunks[0].text.split()[-64:] == chunks[1].text.split()[:64]


def test_long_arabic_sections_are_detected_and_secondary_split_is_bounded():
    sections = [
        f"المادة {i}\n" + " ".join(f"قاعدة{i}_{j}" for j in range(600))
        for i in range(1, 3)
    ]
    chunks = chunk_document(_document("\n".join(sections), "long-ar"), ChunkingConfig(512, 64))
    assert len(chunks) >= 3
    assert all(chunk.text and chunk.token_count <= 512 for chunk in chunks)
    assert any(chunk.section == "المادة 1" for chunk in chunks)
    assert any(chunk.section == "المادة 2" for chunk in chunks)


def test_chunk_id_changes_with_content_and_position():
    base = _document("Article 1\n" + " ".join(f"mot{i}" for i in range(600)), "stable")
    chunks = chunk_document(base, ChunkingConfig(128, 16))
    repeated = chunk_document(base, ChunkingConfig(128, 16))
    changed = chunk_document(_document(base.text + " ajout", "stable"), ChunkingConfig(128, 16))
    assert [chunk.chunk_id for chunk in chunks] == [chunk.chunk_id for chunk in repeated]
    assert chunks[0].chunk_id != chunks[1].chunk_id
    assert chunks[-1].chunk_id != changed[-1].chunk_id
