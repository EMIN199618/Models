"""2. RAG — retrieval, icazələr, təsdiq statusu, mənbə yoxlaması, məlumat çatışmazlığı."""
from app.chains.rag import rag_chain, validate_sources
from app.llm.schemas import RagAnswer
from app.rag.retriever import PgVectorRetriever, format_context, rerank


def _titles(role, q, k=4):
    docs = rerank(q, PgVectorRetriever(role=role, k=10).invoke(q), final_k=k)
    return [d.metadata["title"] for d in docs]


def test_retrieves_relevant_official_document():
    t = _titles("viewer", "Nağd valyutanı hansı məbləğdən bəyan etmək lazımdır?")
    assert any("nağd valyuta" in x.lower() for x in t[:2])


def test_viewer_cannot_see_internal_document_but_analyst_can():
    q = "Cənub ərazi gömrük idarəsi daxili monitorinq müşahidələri"
    assert not any("Daxili qeyd" in x for x in _titles("viewer", q, 8))
    assert any("Daxili qeyd" in x for x in _titles("analyst", q, 8))


def test_pending_document_is_never_retrieved():
    for role in ("viewer", "analyst", "admin"):
        assert not any("Layihə" in x for x in _titles(role, "avtomobil idxalı yeni tarif qaydaları layihəsi", 8))


def test_rag_answer_is_grounded_with_valid_citations():
    r = rag_chain().invoke({"question": "Vətəndaş müraciətinə neçə gün ərzində baxılır?", "role": "viewer", "history": []})
    assert not r.insufficient_evidence
    assert r.citations and all(c.id.startswith("S") for c in r.citations)
    assert "15 iş günü" in r.answer
    assert r.verification in ("official", "mixed")


def test_rag_reports_missing_information_instead_of_inventing():
    r = rag_chain().invoke({"question": "Kosmik gəmilərin orbitə çıxarılması üçün raket yanacağının qiyməti nədir?",
                            "role": "viewer", "history": []})
    assert r.insufficient_evidence is True
    assert r.citations == []


def test_source_validation_strips_fabricated_citations():
    docs = rerank("e-gömrük bəyannamə", PgVectorRetriever(role="viewer", k=5).invoke("e-gömrük bəyannamə"), final_k=2)
    _, refs = format_context(docs)
    fake = RagAnswer(answer="Bəyannamə onlayn verilir [S1]. Uydurma fakt [S9].", citations=["S1", "S9"],
                     insufficient_evidence=False, confidence=0.9)
    out = validate_sources({"llm": fake, "refs": refs, "period": "-"})
    assert "[S9]" not in out.answer
    assert [c.id for c in out.citations] == ["S1"]
    assert out.validation_notes


def test_answer_without_any_valid_source_is_flagged():
    fake = RagAnswer(answer="Hər şey qaydasındadır.", citations=[], insufficient_evidence=False, confidence=0.9)
    docs = PgVectorRetriever(role="viewer", k=2).invoke("gömrük")
    _, refs = format_context(docs)
    out = validate_sources({"llm": fake, "refs": refs, "period": "-"})
    assert out.insufficient_evidence and out.confidence <= 0.3


def test_semantic_search_endpoint_cached_per_role(client):
    from tests.conftest import auth
    q = "/api/search?q=Astara%20narkotik%20qaçaqmalçılıq&k=3"
    r1 = client.get(q, headers=auth("viewer"))
    r2 = client.get(q, headers=auth("viewer"))
    r3 = client.get(q, headers=auth("analyst"))
    assert r1.status_code == 200 and r1.json()["results"]
    assert r2.headers["X-Cache"] == "hit"
    assert r3.headers["X-Cache"] == "miss"  # başqa rol → ayrı keş açarı (icazədən asılı nəticə)
    assert "Astara" in r1.json()["results"][0]["title"]
