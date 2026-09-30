"""Construction déterministe de l'arbre de confiance TrustLens."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import math
import re
from typing import Any, Sequence

from backend.models import (
    Breakdown,
    Branch,
    Claim,
    Document,
    Expert,
    SearchResult,
    SourceOut,
    Stats,
    SuggestedExpert,
    Weights,
)

_AUTHORITY: dict[str, float] = {
    "official_policy": 1.0,
    "procedure": 0.8,
    "expert_note": 0.7,
    "email": 0.4,
    "teams_chat": 0.2,
}
_DEFAULT_WEIGHTS = {"freshness": 0.30, "authority": 0.25, "owner": 0.20, "country": 0.25}


def _as_date(value: str) -> date:
    """Lit une date ISO 8601, avec une erreur de format neutralisée."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.date()


def _normalized_weights(weights: Weights | None) -> dict[str, float]:
    """Normalise les poids pour que leur somme vaille un."""
    if weights is None:
        values = _DEFAULT_WEIGHTS.copy()
    else:
        values = {
            key: float(getattr(weights, key))
            for key in ("freshness", "authority", "owner", "country")
        }
    total = sum(values.values())
    if total <= 0:
        return _DEFAULT_WEIGHTS.copy()
    return {key: value / total for key, value in values.items()}


def _age_years(updated: str, today: date) -> float:
    """Calcule un âge en années sans dépendre d'une bibliothèque externe."""
    days = max(0, (today - _as_date(updated)).days)
    return days / 365.2425


def vectorize(documents: list[Document]) -> tuple[Any, Any]:
    """Fallback TF-IDF local compatible avec la signature de l'axe A.

    À REMPLACER AU MERGE par ``backend.retrieval.vectorize`` de P1.
    """
    texts = [f"{doc.title} {doc.content} {doc.claim}" for doc in documents]
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        local_vectorizer = TfidfVectorizer(lowercase=True, strip_accents="unicode")
        return local_vectorizer.fit_transform(texts), local_vectorizer
    except (ImportError, ValueError):
        # Représentation TF-IDF sparse minimale si scikit-learn n'est pas installé.
        terms_by_document = [re.findall(r"[\wÀ-ÿ]+", text.casefold()) for text in texts]
        document_frequency: dict[str, int] = {}
        for terms in terms_by_document:
            for term in set(terms):
                document_frequency[term] = document_frequency.get(term, 0) + 1
        vectors: list[dict[str, float]] = []
        for terms in terms_by_document:
            frequencies: dict[str, int] = {}
            for term in terms:
                frequencies[term] = frequencies.get(term, 0) + 1
            vector = {
                term: count * (1.0 + math.log((1 + len(documents)) / (1 + document_frequency[term])))
                for term, count in frequencies.items()
            }
            norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
            vectors.append({term: value / norm for term, value in vector.items()})
        return vectors, None


def _cosine_groups(docs: Sequence[Document]) -> list[tuple[int, int]]:
    """Retourne les paires dont la similarité cosinus TF-IDF dépasse 0.9."""
    if len(docs) < 2:
        return []
    try:
        from backend.retrieval import vectorize as shared_vectorize  # type: ignore[import-not-found]
    except (ImportError, AttributeError):
        # À REMPLACER AU MERGE : vectorize() de P1 a la même signature.
        shared_vectorize = vectorize

    try:
        matrix, _vectorizer = shared_vectorize(list(docs))
    except ValueError:
        # Certaines collections sans termes reconnus ne peuvent pas être vectorisées.
        matrix, _vectorizer = vectorize(list(docs))
    pairs: list[tuple[int, int]] = []
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            left = matrix[i]
            right = matrix[j]
            if hasattr(left, "multiply"):
                similarity = float(left.multiply(right).sum())
            elif isinstance(left, dict) and isinstance(right, dict):
                similarity = sum(left.get(term, 0.0) * value for term, value in right.items())
            else:
                similarity = sum(float(a) * float(b) for a, b in zip(left, right))
            if similarity > 0.9:
                pairs.append((i, j))
    return pairs


def _copy_root(doc_id: str, by_id: dict[str, Document]) -> str:
    """Résout les chaînes copy_of en protégeant les cycles et références absentes."""
    seen: set[str] = set()
    current = doc_id
    while current in by_id and current not in seen:
        seen.add(current)
        parent = by_id[current].copy_of
        if not parent:
            break
        current = parent
        if current not in by_id:
            break
    return current


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[\wÀ-ÿ]+", value.casefold()))


def _suggest_expert(
    experts: Sequence[Expert], docs: Sequence[Document], country: str, query: str
) -> SuggestedExpert | None:
    """Choisit l'expert dont les sujets recouvrent le mieux la requête et les titres."""
    context = _tokens(query + " " + " ".join(doc.title for doc in docs))
    best: tuple[int, int, str, Expert] | None = None
    for index, expert in enumerate(experts):
        if expert.country not in (country, "ALL"):
            continue
        topic_tokens = set().union(*(_tokens(topic) for topic in expert.topics)) if expert.topics else set()
        score = len(context & topic_tokens)
        candidate = (score, -index, expert.name, expert)
        if best is None or candidate[:2] > best[:2]:
            best = candidate
    if best is None or best[0] == 0:
        return None
    expert = best[3]
    return SuggestedExpert(name=expert.name, team=expert.team)


def build_tree(
    docs: list[Document],
    claims: list[Claim],
    country: str,
    weights: Weights | None,
    experts: list[Expert],
    query: str = "",
) -> SearchResult:
    """Construit les branches, scores, avertissements et expert suggéré.

    Le calcul est déterministe pour des entrées identiques et n'appelle aucun LLM.
    ``query`` est facultatif pour rester compatible avec la signature partagée.
    """
    if not docs:
        return SearchResult(
            status="low", answer=None, confidence=0.0, branches=[],
            stats=Stats(reliable_docs_pct=0.0, total_docs=0, reliable_docs=0, duplicates_collapsed=0),
            warnings=[], suggested_expert=None,
        )

    today = date.today()
    normalized = _normalized_weights(weights)
    by_id = {doc.id: doc for doc in docs}
    claims_by_id = {claim.doc_id: claim for claim in claims if claim.doc_id in by_id}
    grouped_claims: dict[str, list[tuple[Document, Claim]]] = {}
    for claim in claims:
        doc = by_id.get(claim.doc_id)
        if doc is not None:
            grouped_claims.setdefault(claim.normalized_value, []).append((doc, claim))

    warnings: list[str] = []
    source_scores: dict[str, tuple[float, Breakdown, bool, bool, bool, str]] = {}
    for doc in docs:
        claim = claims_by_id.get(doc.id)
        suspicious = bool(claim and claim.suspicious)
        age = _age_years(doc.last_updated, today)
        breakdown = Breakdown(
            freshness=0.5 ** (age / 2.0),
            authority=_AUTHORITY.get(doc.source_type, 0.0),
            owner=1.0 if doc.owner else 0.3,
            country=1.0 if doc.country in (country, "ALL") else 0.2,
        )
        score = sum(normalized[key] * getattr(breakdown, key) for key in normalized)
        if doc.expert_validated:
            score = min(1.0, score + 0.10)
        if suspicious:
            score *= 0.1
        review_date: date | None = None
        if doc.review_due:
            try:
                review_date = _as_date(doc.review_due)
            except ValueError:
                review_date = None
        expiring = review_date is not None and 0 <= (review_date - today).days <= 60
        source_scores[doc.id] = (score, breakdown, suspicious, bool(claim and claim.needs_review), expiring, doc.claim_quote)
        if not doc.owner:
            warnings.append(f"Document sans propriétaire : {doc.title}")
        if doc.country not in (country, "ALL"):
            warnings.append(f"Document possiblement d'un autre pays : {doc.title}")
        if age > 3:
            warnings.append(f"Document vieux de {int(age)} ans : {doc.title}")
        if suspicious:
            warnings.append(f"Document suspect (tentative d'injection détectée) : {doc.title}")
        if review_date is not None and review_date <= today + timedelta(days=60):
            warnings.append(f"Information à réviser avant le {doc.review_due} : {doc.title}")
        if claim and claim.needs_review:
            warnings.append(f"Affirmation à vérifier : {doc.title}")

    branches: list[Branch] = []
    duplicates_collapsed = 0
    for value, items in grouped_claims.items():
        branch_docs = [doc for doc, _claim in items]
        parent = list(range(len(branch_docs)))

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left: int, right: int) -> None:
            root_left, root_right = find(left), find(right)
            if root_left != root_right:
                parent[root_right] = root_left

        roots: dict[str, int] = {}
        for index, doc in enumerate(branch_docs):
            root = _copy_root(doc.id, by_id)
            if root in roots:
                union(index, roots[root])
            else:
                roots[root] = index
        for left, right in _cosine_groups(branch_docs):
            union(left, right)

        clusters: dict[int, list[int]] = {}
        for index in range(len(branch_docs)):
            clusters.setdefault(find(index), []).append(index)
        selected: set[int] = set()
        for members in clusters.values():
            winner = max(members, key=lambda i: (source_scores[branch_docs[i].id][0], -i))
            selected.add(winner)
            duplicates_collapsed += len(members) - 1

        sources: list[SourceOut] = []
        branch_contributors: list[float] = []
        for index, (doc, claim) in enumerate(items):
            score, breakdown, suspicious, needs_review, expiring, quote = source_scores[doc.id]
            duplicate = index not in selected
            sources.append(SourceOut(
                doc_id=doc.id, title=doc.title, score=score, breakdown=breakdown,
                is_duplicate=duplicate, quote=quote or claim.quote,
                needs_review=needs_review, suspicious=suspicious, expiring_soon=expiring,
            ))
            if not duplicate and score > 0.25:
                branch_contributors.append(score)
        branch_score = 1.0 - math.prod(1.0 - score for score in branch_contributors)
        branch_claim = max(items, key=lambda pair: source_scores[pair[0].id][0])[1]
        branches.append(Branch(
            value=value, claim_text=branch_claim.claim_text, score=branch_score, share=0.0,
            sources=sorted(sources, key=lambda source: source.score, reverse=True),
        ))

    branches.sort(key=lambda branch: branch.score, reverse=True)
    total_score = sum(branch.score for branch in branches)
    if total_score > 0:
        for branch in branches:
            branch.share = branch.score / total_score * 100.0
    confidence = branches[0].share if branches else 0.0
    second_share = branches[1].share if len(branches) > 1 else 0.0
    if not branches or max(branch.score for branch in branches) <= 0.40:
        status = "low"
    elif confidence > 70.0 and confidence - second_share > 25.0:
        status = "confident"
    else:
        status = "conflict"

    reliable_docs = sum(1 for score, *_rest in source_scores.values() if score > 0.6)
    all_docs = list(docs)
    suggested = None if status == "confident" else _suggest_expert(experts, all_docs, country, query)
    if not query:
        query = " ".join(doc.title for doc in docs)
        if suggested is None and status != "confident":
            suggested = _suggest_expert(experts, all_docs, country, query)

    return SearchResult(
        status=status,
        answer=branches[0].claim_text if status == "confident" and branches else None,
        confidence=confidence,
        branches=branches,
        stats=Stats(
            reliable_docs_pct=reliable_docs / len(docs) * 100.0,
            total_docs=len(docs), reliable_docs=reliable_docs,
            duplicates_collapsed=duplicates_collapsed,
        ),
        warnings=list(dict.fromkeys(warnings)),
        suggested_expert=suggested,
    )
