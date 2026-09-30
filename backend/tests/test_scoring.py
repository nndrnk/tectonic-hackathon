"""Tests du scoring et de l'arbre de décision TrustLens."""

from datetime import date as RealDate

import pytest

import backend.tree as tree_module
from backend.models import Claim, Document, Expert, SearchResult, Weights
from backend.tree import build_tree


class FixedDate(RealDate):
    """Date contrôlée pour éviter toute dépendance à l'horloge réelle."""

    @classmethod
    def today(cls) -> "FixedDate":
        return cls(2025, 1, 1)


@pytest.fixture(autouse=True)
def fixed_system_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tree_module, "date", FixedDate)


def make_doc(
    doc_id: str,
    *,
    title: str | None = None,
    source_type: str = "official_policy",
    country: str = "BE",
    owner: str | None = "Équipe RH",
    updated: str = "2024-12-01",
    copy_of: str | None = None,
    value: str = "valeur_a",
    validated: bool = False,
) -> Document:
    """Construit une pièce de test sans dépendance aux données du projet."""
    return Document(
        id=doc_id,
        title=title or f"Document {doc_id}",
        content=f"La règle {value} est documentée pour {doc_id}.",
        source_type=source_type,
        owner=owner,
        country=country,
        last_updated=updated,
        copy_of=copy_of,
        claim=f"La règle {value} s'applique.",
        claim_quote=f"La règle {value} est documentée.",
        normalized_value=value,
        access_level="employee",
        expert_validated=validated,
        review_due=None,
    )


def make_claim(
    doc: Document,
    *,
    value: str | None = None,
    text: str | None = None,
    suspicious: bool = False,
    needs_review: bool = False,
) -> Claim:
    return Claim(
        doc_id=doc.id,
        claim_text=text or doc.claim,
        normalized_value=value or doc.normalized_value,
        quote=doc.claim_quote,
        suspicious=suspicious,
        needs_review=needs_review,
    )


def run_tree(
    docs: list[Document],
    claims: list[Claim] | None = None,
    *,
    weights: Weights | None = None,
    experts: list[Expert] | None = None,
) -> SearchResult:
    return build_tree(
        docs=docs,
        claims=claims if claims is not None else [make_claim(doc) for doc in docs],
        country="BE",
        weights=weights,
        experts=experts or [],
    )


def test_three_old_copies_lose_to_one_recent_official_document() -> None:
    copies = [
        make_doc("root", source_type="teams_chat", country="FR", owner=None, updated="2017-01-01", value="ancienne"),
        make_doc("copy-b", source_type="teams_chat", country="FR", owner=None, updated="2018-01-01", value="ancienne", copy_of="root"),
        make_doc("copy-c", source_type="teams_chat", country="FR", owner=None, updated="2019-01-01", value="ancienne", copy_of="root"),
    ]
    official = make_doc("official", source_type="official_policy", updated="2024-12-01", value="actuelle")
    result = run_tree(copies + [official])

    assert result.status == "confident"
    assert result.answer == official.claim
    assert result.branches[0].value == "actuelle"
    old_branch = next(branch for branch in result.branches if branch.value == "ancienne")
    assert sum(source.is_duplicate for source in old_branch.sources) == 2
    assert result.stats.duplicates_collapsed == 2


def test_two_similar_branches_are_reported_as_conflict() -> None:
    first = make_doc("a", value="option_a")
    second = make_doc("b", value="option_b")
    result = run_tree([first, second])

    assert result.status == "conflict"
    assert result.answer is None
    assert len(result.branches) == 2
    assert result.branches[0].share == pytest.approx(50.0)
    assert result.branches[1].share == pytest.approx(50.0)


def test_other_country_document_gets_a_lower_score() -> None:
    local = make_doc("local", country="BE")
    foreign = make_doc("foreign", country="FR", value="foreign_value")
    result = run_tree([local, foreign])
    local_score = result.branches[0].sources[0].score
    foreign_branch = next(branch for branch in result.branches if branch.value == foreign.normalized_value)

    assert foreign_branch.sources[0].score < local_score
    assert "Document possiblement d'un autre pays : Document foreign" in result.warnings


def test_suspicious_claim_is_strongly_penalized() -> None:
    doc = make_doc("unsafe")
    safe = run_tree([doc])
    suspicious = run_tree([doc], [make_claim(doc, suspicious=True)])

    assert suspicious.branches[0].sources[0].suspicious is True
    assert suspicious.branches[0].sources[0].score == pytest.approx(safe.branches[0].sources[0].score * 0.1)
    assert suspicious.branches[0].score == 0.0
    assert suspicious.status == "low"


def test_custom_weights_can_change_the_winning_branch() -> None:
    old_official = make_doc("old-policy", source_type="official_policy", updated="2022-01-01", value="policy")
    recent_chat = make_doc("recent-chat", source_type="teams_chat", updated="2024-12-01", value="chat")
    authority_weighted = run_tree(
        [old_official, recent_chat],
        weights=Weights(freshness=0.0, authority=1.0, owner=0.0, country=0.0),
    )
    freshness_weighted = run_tree(
        [old_official, recent_chat],
        weights=Weights(freshness=1.0, authority=0.0, owner=0.0, country=0.0),
    )

    assert authority_weighted.branches[0].value == "policy"
    assert freshness_weighted.branches[0].value == "chat"


def test_no_documents_returns_low_result_without_error() -> None:
    result = run_tree([])

    assert result.status == "low"
    assert result.answer is None
    assert result.confidence == 0
    assert result.branches == []
    assert result.stats.total_docs == 0


def test_branch_shares_sum_to_one_hundred() -> None:
    docs = [make_doc("a", value="a"), make_doc("b", value="b"), make_doc("c", value="c")]
    result = run_tree(docs)

    assert sum(branch.share for branch in result.branches) == pytest.approx(100.0)


def test_many_weak_sources_cannot_create_a_confident_branch() -> None:
    docs = [
        make_doc(f"chat-{index}", source_type="teams_chat", value="faible")
        for index in range(12)
    ]
    result = run_tree(
        docs,
        weights=Weights(freshness=0.0, authority=1.0, owner=0.0, country=0.0),
    )

    assert all(source.score == pytest.approx(0.2) for source in result.branches[0].sources)
    assert result.branches[0].score == 0.0
    assert result.status == "low"
