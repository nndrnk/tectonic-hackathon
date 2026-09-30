"""
Tests de sécurité Axe C — pytest + TestClient, aucun appel réseau réel.

Prérequis : backend/models.py (axe B) doit exister (contrat Pydantic).
Exécution depuis la racine du repo :  pytest backend/tests/test_security.py

Cas du contrat :
 (a) sans JWT -> 401                     (j) aucune stack trace dans les réponses
 (b) JWT expiré -> 401                   (k) masquage PII : email, IBAN, téléphone
 (c) employee ne voit jamais un doc      (l) CORS refuse une origine inconnue
     payroll_expert                      (m) en-têtes de sécurité présents
 (d) query 10 000 caractères -> 422      (n) clé API et mot de passe absents des logs
 (e) country invalide -> 422             (o) employee ne peut pas valider un document
 (f) champ inconnu -> 422                (p) corps > 20 Ko -> 413
 (g1) 6 logins en rafale -> 429          (q) subject transmis à retrieve (mock)
 (g2) verrouillage après 5 échecs
 (h) document piégé neutralisé
 (i) rate limit /search -> 429
"""

import os
import sys
from pathlib import Path
from typing import Any, Optional

# Racine du repo sur sys.path : permet "import backend..." depuis partout
ROOT: Path = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Configuration AVANT l'import de backend.main (qui valide JWT_SECRET)
os.environ.setdefault("JWT_SECRET", "0123456789abcdef0123456789abcdef")
os.environ.setdefault("USE_STUBS", "true")
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:5173")
os.environ.pop("BACKEND_PUBLIC_URL", None)

from datetime import datetime, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt as jose_jwt  # noqa: E402

import backend.main as main  # noqa: E402
from backend import security  # noqa: E402

SECRET: str = main.app.state.jwt_secret

# raise_server_exceptions=False : le handler global d'exceptions doit produire
# une réponse 500, pas faire échouer le test par une exception (cas j).
client: TestClient = TestClient(main.app, raise_server_exceptions=False)

# Comptes de démonstration (documentés dans README.md et SECURITY.md)
PASSWORDS: dict[str, str] = {
    "alice": "Alice!Demo2026",
    "bob": "Bob!Demo2026",
    "chloe": "Chloe!Demo2026",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Isole chaque test : rate limiter, verrouillages et votes remis à zéro."""
    main.limiter.reset()
    security.reset_login_state()
    main._feedback_votes.clear()
    main._expert_validations.clear()
    yield
    main.limiter.reset()
    security.reset_login_state()
    main._feedback_votes.clear()
    main._expert_validations.clear()


def login(username: str, password: Optional[str] = None) -> dict[str, str]:
    """Connexion réelle via /auth/login ; retourne les en-têtes Authorization."""
    response = client.post(
        "/auth/login",
        json={"username": username, "password": password or PASSWORDS[username]},
    )
    assert response.status_code == 200, f"login {username}: {response.text}"
    token: str = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_token(username: str, role: str, expired: bool = False) -> str:
    """Fabrique un JWT à la main (pour tester expiration et rôles)."""
    now: datetime = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": username,
        "role": role,
        "iat": int(now.timestamp()) - (4000 if expired else 0),
        "exp": int(now.timestamp()) + (-2000 if expired else 1800),
    }
    return jose_jwt.encode(payload, SECRET, algorithm="HS256")


SEARCH_OK: dict[str, str] = {
    "query": "duree de preavis travailleur",
    "country": "BE",
    "subject": "worker",
}


# ---------------------------------------------------------------------------
# (a) Sans JWT -> 401
# ---------------------------------------------------------------------------

def test_a_sans_jwt_401() -> None:
    response = client.post("/search", json=SEARCH_OK)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# (b) JWT expiré -> 401
# ---------------------------------------------------------------------------

def test_b_jwt_expire_401() -> None:
    headers: dict[str, str] = {"Authorization": f"Bearer {make_token('alice', 'employee', expired=True)}"}
    response = client.post("/search", json=SEARCH_OK, headers=headers)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# (c) employee ne reçoit jamais un document payroll_expert
# ---------------------------------------------------------------------------

def test_c_employee_ne_voit_pas_doc_payroll_expert() -> None:
    headers: dict[str, str] = login("alice")
    # Requête qui matche le document confidentiel doc-be-004
    response = client.post(
        "/search",
        json={"query": "grille salariale", "country": "BE", "subject": "worker"},
        headers=headers,
    )
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    doc_ids: list[str] = [
        source["doc_id"] for branch in body["branches"] for source in branch["sources"]
    ]
    assert "doc-be-004" not in doc_ids, "Fuite : document payroll_expert visible par un employee"
    # Double contrôle : requête générique "preavis" non plus
    response2 = client.post("/search", json=SEARCH_OK, headers=headers)
    doc_ids2: list[str] = [
        source["doc_id"]
        for branch in response2.json()["branches"]
        for source in branch["sources"]
    ]
    assert "doc-be-004" not in doc_ids2


# ---------------------------------------------------------------------------
# (d) Query de 10 000 caractères -> 422
# ---------------------------------------------------------------------------

def test_d_query_10000_caracteres_422() -> None:
    headers: dict[str, str] = login("alice")
    body: dict[str, Any] = {**SEARCH_OK, "query": "x" * 10000}
    response = client.post("/search", json=body, headers=headers)
    assert response.status_code == 422
    # La valeur saisie ne doit jamais être renvoyée
    assert "x" * 50 not in response.text


# ---------------------------------------------------------------------------
# (e) Country invalide -> 422
# ---------------------------------------------------------------------------

def test_e_country_invalide_422() -> None:
    headers: dict[str, str] = login("alice")
    response = client.post(
        "/search", json={**SEARCH_OK, "country": "XX"}, headers=headers
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# (f) Champ inconnu -> 422 (extra="forbid" dans models.py)
# ---------------------------------------------------------------------------

def test_f_champ_inconnu_422() -> None:
    headers: dict[str, str] = login("alice")
    response = client.post(
        "/search", json={**SEARCH_OK, "champ_inconnu": 1}, headers=headers
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# (g1) 6 logins en rafale, même IP -> 429 (rate limit slowapi)
# ---------------------------------------------------------------------------

def test_g1_login_en_rafale_429() -> None:
    codes: list[int] = [
        client.post(
            "/auth/login", json={"username": "alice", "password": PASSWORDS["alice"]}
        ).status_code
        for _ in range(6)
    ]
    assert codes[:5] == [200] * 5, f"5 premiers logins attendus en 200 : {codes}"
    assert codes[5] == 429, f"6e login attendu en 429 : {codes}"


# ---------------------------------------------------------------------------
# (g2) 5 échecs -> verrouillage ; ensuite même le bon mot de passe échoue
#      avec le message générique (rate limiting désactivé pour isoler)
# ---------------------------------------------------------------------------

def test_g2_verrouillage_apres_5_echecs() -> None:
    # Rate limit désactivé pour isoler le verrouillage applicatif
    main.limiter.enabled = False
    try:
        # 5 échecs avec un mauvais mot de passe
        for _ in range(5):
            response = client.post(
                "/auth/login",
                json={"username": "alice", "password": "MauvaisMot1!"},
            )
            assert response.status_code == 401
            assert response.json()["detail"] == "Identifiants invalides"
        # 6e tentative : verrouillé, même avec le BON mot de passe
        response = client.post(
            "/auth/login", json={"username": "alice", "password": PASSWORDS["alice"]}
        )
        assert response.status_code == 429
        assert response.json()["detail"] == "Trop de tentatives. Réessayez plus tard."
        # Utilisateur inexistant : même 429 générique (pas de divulgation)
        response = client.post(
            "/auth/login", json={"username": "inconnu", "password": "Quelconque1!"}
        )
        assert response.status_code == 401  # pas encore verrouillé : générique 401
        for _ in range(5):
            client.post(
                "/auth/login", json={"username": "inconnu", "password": "Quelconque1!"}
            )
        response = client.post(
            "/auth/login", json={"username": "inconnu", "password": "Quelconque1!"}
        )
        assert response.status_code == 429
    finally:
        main.limiter.enabled = True


# ---------------------------------------------------------------------------
# (h) Document piégé détecté (suspicious) et sans influence
# ---------------------------------------------------------------------------

def test_h_document_piege_neutralise() -> None:
    headers: dict[str, str] = login("alice")
    response = client.post("/search", json=SEARCH_OK, headers=headers)
    assert response.status_code == 200
    body: dict[str, Any] = response.json()

    suspicious_sources: list[dict[str, Any]] = [
        source
        for branch in body["branches"]
        for source in branch["sources"]
        if source["suspicious"]
    ]
    # doc-be-006 (injection de prompt) est bien détecté
    assert any(s["doc_id"] == "doc-be-006" for s in suspicious_sources)
    # ... mais sans influence : score 0, avertissement, réponse non détournée
    for source in suspicious_sources:
        assert source["score"] == 0.0
    assert any(
        "injection" in warning.lower() for warning in body["warnings"]
    )
    assert body["answer"] is not None and "12 mois" not in body["answer"]


# ---------------------------------------------------------------------------
# (i) Rate limit /search (30/min/IP) -> 429
# ---------------------------------------------------------------------------

def test_i_rate_limit_search_429() -> None:
    headers: dict[str, str] = login("alice")
    codes: list[int] = [
        client.post("/search", json=SEARCH_OK, headers=headers).status_code
        for _ in range(31)
    ]
    assert 200 in codes and 429 in codes
    assert codes[0] == 200
    assert codes[-1] == 429


# ---------------------------------------------------------------------------
# (j) Aucune stack trace dans les réponses (500 générique + corrélation)
# ---------------------------------------------------------------------------

def test_j_pas_de_stack_trace() -> None:
    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("DÉTAIL_INTERNE_SECRET_12345")

    original = main.pipeline.build_tree
    main.pipeline.build_tree = _boom
    try:
        headers: dict[str, str] = login("alice")
        response = client.post("/search", json=SEARCH_OK, headers=headers)
        assert response.status_code == 500
        text: str = response.text
        assert "Traceback" not in text
        assert "DÉTAIL_INTERNE_SECRET_12345" not in text
        assert "Référence" in text  # ID de corrélation présent
    finally:
        main.pipeline.build_tree = original


# ---------------------------------------------------------------------------
# (k) Masquage PII : emails, IBAN, téléphones
# ---------------------------------------------------------------------------

def test_k_masquage_pii() -> None:
    headers: dict[str, str] = login("alice")
    texte: str = (
        "Bonjour, je suis jean.dupont@example.com, mon IBAN est BE71 0961 2345 6769 "
        "et mon numéro est +32 475 12 34 56. Le préavis est de 2 mois selon cet email."
    )
    response = client.post(
        "/analyze-text", json={"text": texte, "country": "BE"}, headers=headers
    )
    assert response.status_code == 200
    text: str = response.text
    assert "jean.dupont@example.com" not in text
    assert "BE71 0961 2345 6769" not in text
    assert "+32 475 12 34 56" not in text
    assert "[EMAIL MASQUÉ]" in text
    assert "[IBAN MASQUÉ]" in text
    assert "[TÉLÉPHONE MASQUÉ]" in text


# ---------------------------------------------------------------------------
# (l) CORS refuse une origine inconnue
# ---------------------------------------------------------------------------

def test_l_cors_origine_inconnue_refusee() -> None:
    response = client.options(
        "/search",
        headers={
            "Origin": "https://site-malveillant.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    # Aucun en-tête CORS autorisant n'est renvoyé pour une origine inconnue
    assert response.headers.get("access-control-allow-origin") is None
    # L'origine autorisée fonctionne, et "*" n'est jamais utilisé
    response_ok = client.options(
        "/search",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response_ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response_ok.headers.get("access-control-allow-origin") != "*"


# ---------------------------------------------------------------------------
# (m) En-têtes de sécurité présents
# ---------------------------------------------------------------------------

def test_m_en_tetes_de_securite() -> None:
    response = client.get("/health")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("referrer-policy") == "no-referrer"
    assert "strict-transport-security" in response.headers
    csp: str = response.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    # Réponse authentifiée : jamais mise en cache
    headers: dict[str, str] = login("alice")
    auth_response = client.post("/search", json=SEARCH_OK, headers=headers)
    assert auth_response.headers.get("cache-control") == "no-store"


# ---------------------------------------------------------------------------
# (n) Clé API et mot de passe absents des logs
# ---------------------------------------------------------------------------

def test_n_secrets_absents_des_logs(caplog: Any) -> None:
    import logging

    with caplog.at_level(logging.INFO, logger="backend.audit"):
        with caplog.at_level(logging.INFO, logger="backend.security"):
            # Login : le mot de passe transite par la requête
            client.post(
                "/auth/login",
                json={"username": "alice", "password": "Alice!Demo2026"},
            )
            # analyze-text contenant une fausse clé API
            headers: dict[str, str] = login("alice")
            token: str = headers["Authorization"].split(" ")[1]
            client.post(
                "/analyze-text",
                json={
                    "text": "Ma clé api_key sk-ABCDEF123456789 personnel. "
                            "Le préavis est de 2 mois.",
                    "country": "BE",
                },
                headers=headers,
            )
    logs: str = caplog.text
    assert "Alice!Demo2026" not in logs, "Mot de passe présent dans les logs"
    assert "sk-ABCDEF123456789" not in logs, "Clé API présente dans les logs"
    assert token not in logs, "Token JWT présent dans les logs"


# ---------------------------------------------------------------------------
# (o) employee ne peut pas valider un document (expert_validated)
# ---------------------------------------------------------------------------

def test_o_employee_ne_peut_pas_valider() -> None:
    alice_headers: dict[str, str] = login("alice")
    response = client.post(
        "/feedback",
        json={"doc_id": "doc-be-001", "vote": "useful"},
        headers=alice_headers,
    )
    assert response.status_code == 200
    assert response.json()["expert_validated"] is False, (
        "Un employee a fait passer expert_validated à True"
    )
    # Double vote refusé (409), un vote par (username, doc_id)
    response_dup = client.post(
        "/feedback",
        json={"doc_id": "doc-be-001", "vote": "wrong"},
        headers=alice_headers,
    )
    assert response_dup.status_code == 409
    # Seul payroll_expert peut valider
    chloe_headers: dict[str, str] = login("chloe")
    response_expert = client.post(
        "/feedback",
        json={"doc_id": "doc-be-001", "vote": "useful"},
        headers=chloe_headers,
    )
    assert response_expert.status_code == 200
    assert response_expert.json()["expert_validated"] is True


# ---------------------------------------------------------------------------
# (p) Corps > 20 Ko -> 413
# ---------------------------------------------------------------------------

def test_p_corps_trop_volumineux_413() -> None:
    headers: dict[str, str] = login("alice")
    response = client.post(
        "/analyze-text",
        json={"text": "x" * 21000, "country": "BE"},
        headers=headers,
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "Corps de requête trop volumineux"


# ---------------------------------------------------------------------------
# (q) subject transmis à retrieve (mock)
# ---------------------------------------------------------------------------

def test_q_subject_transmis_a_retrieve(monkeypatch: Any) -> None:
    calls: list[dict[str, Any]] = []

    def mock_retrieve(*args: Any, **kwargs: Any) -> list[Any]:
        calls.append(kwargs)
        # On retourne les documents du stub (sans interpretation du mock)
        return main.pipeline.load_documents()[:1]

    monkeypatch.setattr(main.pipeline, "retrieve", mock_retrieve)
    headers: dict[str, str] = login("alice")
    response = client.post(
        "/search",
        json={**SEARCH_OK, "subject": "group"},
        headers=headers,
    )
    assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0]["subject"] == "group", "subject non transmis tel quel à retrieve"
    # Le rôle du token (pas d'un éventuel champ du corps) est transmis
    assert calls[0]["role"] == "employee"


# ---------------------------------------------------------------------------
# Compléments hors contrat : démarrage refusé sans JWT_SECRET valide
# ---------------------------------------------------------------------------

def test_config_jwt_secret_invalide_refuse() -> None:
    with pytest.raises(RuntimeError):
        security.validate_runtime_config(None)
    with pytest.raises(RuntimeError):
        security.validate_runtime_config("court")
    assert security.validate_runtime_config("0" * 32) == "0" * 32


# ---------------------------------------------------------------------------
# Liaison ADC (Google Cloud) : backend/gcp.py
# ---------------------------------------------------------------------------

def test_adc_absent_erreur_documentee(monkeypatch: Any) -> None:
    """Sans ADC, erreur française avec instructions — jamais de secret."""
    import google.auth

    from backend import gcp

    def _no_adc(*args: Any, **kwargs: Any) -> Any:
        raise google.auth.exceptions.DefaultCredentialsError("no creds")

    monkeypatch.setattr(gcp.google.auth, "default", _no_adc)
    with pytest.raises(gcp.GoogleCloudADCError) as excinfo:
        gcp.get_adc_credentials()
    message: str = str(excinfo.value)
    assert "gcloud auth application-default login" in message
    # Aucune clé ni credential dans le message d'erreur
    assert "AIza" not in message and "private_key" not in message


def test_adc_relie_via_compte_de_service(monkeypatch: Any, tmp_path: Any) -> None:
    """Chaîne ADC réelle : GOOGLE_APPLICATION_CREDENTIALS -> compte de service.

    Le JSON factice est généré dans tmp_path (dossier temporaire de pytest,
    hors du repo) avec une clé RSA neuve : aucune clé réelle n'est utilisée.
    """
    import json

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from google.oauth2 import service_account

    from backend import gcp

    # Clé RSA éphémère, générée pour le test uniquement
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem: str = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    info: dict[str, Any] = {
        "type": "service_account",
        "project_id": "hackathon-poc-test",
        "private_key_id": "cle-test-ephemere",
        "private_key": pem,
        "client_email": "test@hackathon-poc-test.iam.googleapis.com",
        "client_id": "123456789",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    sa_file = tmp_path / "sa-factice.json"
    sa_file.write_text(json.dumps(info), encoding="utf-8")

    # ADC priorise GOOGLE_APPLICATION_CREDENTIALS (chaîne réelle, sans mock)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(sa_file))
    credentials, project = gcp.get_adc_credentials()
    assert isinstance(credentials, service_account.Credentials)
    assert credentials.project_id == "hackathon-poc-test"
    assert project == "hackathon-poc-test"
    # Le fichier factice ne doit jamais finir dans le repo : il est dans tmp_path
    assert "hackathon" not in str(sa_file.parent) or ".pytest" in str(sa_file.parent)
