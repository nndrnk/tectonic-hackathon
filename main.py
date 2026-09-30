"""
API Axe C — backend FastAPI (dev local : http://localhost:8000, déployable
sur Cloud Run : stateless, secrets via Secret Manager).

Endpoints :
    GET  /health          : probe Cloud Run, rien de sensible
    POST /auth/login      : JWT 30 min (bcrypt + verrouillage)
    POST /search          : recherche pondérée (JWT requis)
    POST /analyze-text    : analyse d'un texte libre (JWT requis, non persisté)
    POST /feedback        : vote utile/incorrect (JWT requis, en mémoire)

Bascule USE_STUBS (défaut "true") : pipeline = backend.stubs.
"false" : pipeline = backend.claims (axe A) qui doit exporter les mêmes
signatures : load_documents, load_experts, retrieve, extract_claims,
detect_injection, build_tree. Aucune autre ligne de main.py ne change.

Sécurité : CORS restrictif (jamais "*"), rate limiting slowapi, middlewares
de security.py (en-têtes + limite 20 Ko), handler générique d'exceptions,
journal d'audit sans secret. Voir SECURITY.md.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, cast

# Charger .env (racine du repo) AVANT toute lecture d'os.environ.
# Le .env est ignoré par git : c'est le seul endroit local pour les secrets
# (JWT_SECRET, ANTHROPIC_API_KEY, GOOGLE_API_KEY). En production, ces valeurs
# viennent de Secret Manager via la config Cloud Run — pas d'un fichier .env.
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# NOTE : pas de "from __future__ import annotations" ici — combiné au décorateur
# slowapi, FastAPI ne résout plus les annotations des corps Pydantic et traite
# le paramètre comme un query param (422 "missing"). Vérifié au 2026-09-30.

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.status import (
    HTTP_401_UNAUTHORIZED,
    HTTP_409_CONFLICT,
    HTTP_429_TOO_MANY_REQUESTS,
)

from backend import security
from backend.models import (
    AnalyzeTextRequest,
    Document,
    FeedbackRequest,
    LoginRequest,
    Role,
    SearchRequest,
    SearchResult,
    TokenResponse,
)

# ---------------------------------------------------------------------------
# Configuration (variables d'env ; secrets JAMAIS en dur dans le repo)
# ---------------------------------------------------------------------------

# En production : JWT_SECRET injecté par Secret Manager (config Cloud Run).
# Le démarrage est refusé si absent ou < 32 caractères.
JWT_SECRET: str = security.validate_runtime_config(os.getenv("JWT_SECRET"))

# Origine autorisée du frontend (jamais "*" : CORS restrictif)
FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").strip()

# URL publique du backend (CSP connect-src) si déployé sur Cloud Run
BACKEND_PUBLIC_URL: Optional[str] = os.getenv("BACKEND_PUBLIC_URL") or None

# Bascule stubs <-> vrais modules des axes A et B (défaut : stubs)
USE_STUBS: bool = os.getenv("USE_STUBS", "true").strip().lower() == "true"

if USE_STUBS:
    from backend import stubs as pipeline
else:
    # Vraies implémentations (axe A) : mêmes signatures que stubs.py.
    # claims.py n'existe pas encore (livré par l'axe A) et le nom pipeline
    # est lié conditionnellement : ignores mypy volontaires.
    from backend import claims as pipeline  # type: ignore[no-redef,attr-defined]

# ---------------------------------------------------------------------------
# Liaison ADC (Google Cloud) : informative, jamais bloquante.
# En mode stubs, l'API tourne sans GCP ; en mode réel (axe A) ou en prod,
# claims.py appelle backend.gcp.get_adc_credentials().
# ---------------------------------------------------------------------------
import logging

from backend import gcp

logging.basicConfig(level=logging.INFO)
_logger: logging.Logger = logging.getLogger("backend.main")
try:
    _adc_creds, _adc_project = gcp.get_adc_credentials()
    # Le project ID n'est pas un secret ; jamais de credential en log
    _logger.info("Liaison ADC Google Cloud active, projet=%s", _adc_project)
except gcp.GoogleCloudADCError:
    _logger.info(
        "Liaison ADC Google Cloud absente (facultative en mode stubs) : "
        "gcloud auth application-default login pour l'activer"
    )

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app: FastAPI = FastAPI(
    title="Payroll Policies API",
    description="Recherche pondérée de politiques RH (PoC hackathon, axe C).",
    version="1.0.0",
)

# Secret JWT validé, disponible pour les dépendances de security.py
app.state.jwt_secret = JWT_SECRET

# CORS restrictif : uniquement FRONTEND_ORIGIN, méthodes GET/POST,
# en-têtes Authorization et Content-Type. Jamais "*" ni allow_credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# En-têtes de sécurité + limite de corps 20 Ko (security.py)
app.add_middleware(security.SecurityHeadersMiddleware, backend_public_url=BACKEND_PUBLIC_URL)
app.add_middleware(security.BodySizeLimitMiddleware)

# Toute exception non gérée -> 500 générique + ID de corrélation
app.add_exception_handler(Exception, security.generic_exception_handler)

# Rate limiting slowapi (limites par IP ; limite PoC derrière le LB Cloud Run,
# voir SECURITY.md : l'IP vue peut être celle du load balancer)
limiter: Limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """429 propre : message générique, aucune information interne."""
    return JSONResponse(
        status_code=HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Trop de requêtes. Réessayez plus tard."},
        headers={"Retry-After": "60"},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 SANS jamais renvoyer la valeur saisie (anti-écho / anti-fuite)."""
    details: list[dict[str, Any]] = []
    for error in exc.errors():
        details.append(
            {
                "loc": error.get("loc", []),
                "msg": "Valeur invalide",
                "type": error.get("type", "invalid"),
            }
        )
    return JSONResponse(status_code=422, content={"detail": details})


# ---------------------------------------------------------------------------
# État en mémoire (STATELESS, exigence Cloud Run) — limites documentées
# dans SECURITY.md : feedback et verrouillages sont propres à chaque instance.
# ---------------------------------------------------------------------------

# Feedback : un vote par (username, doc_id)
_feedback_votes: set[tuple[str, str]] = set()
# Validation expert en mémoire : {doc_id: True} — seul payroll_expert peut
# passer expert_validated à True ; le score n'est JAMAIS modifié.
_expert_validations: dict[str, bool] = {}

# Seul accès fichier autorisé du service : backend/data/users.json
USERS_FILE: Path = Path(__file__).resolve().parent / "data" / "users.json"


def _load_users() -> list[dict[str, str]]:
    """Charge les comptes depuis backend/data/users.json (hashs bcrypt)."""
    with USERS_FILE.open(encoding="utf-8") as f:
        users: Any = json.load(f)
    return users


def _content_length(request: Request) -> int:
    """Longueur du corps (métadonnée d'audit uniquement)."""
    raw: Optional[str] = request.headers.get("content-length")
    try:
        return int(raw) if raw else 0
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# GET /health — probe Cloud Run, rien de sensible
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, str]:
    """Sonde de santé (utilisée par Cloud Run comme probe)."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /auth/login — JWT 30 min
# ---------------------------------------------------------------------------

@app.post("/auth/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest) -> Any:
    """Authentifie un utilisateur de users.json et délivre un JWT HS256.

    Mesures : message générique unique (pas de divulgation de l'existence du
    compte), verrouillage 5 minutes après 5 échecs (security.py), audit sans
    mot de passe ni token.
    """
    # Verrouillage temporaire : même message pour tout utilisateur (429)
    if security.is_locked_out(body.username):
        security.audit(body.username, "inconnu", "/auth/login", _content_length(request), HTTP_429_TOO_MANY_REQUESTS)
        return JSONResponse(
            status_code=HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": security.GENERIC_LOCKED_ERROR},
        )

    user: Optional[dict[str, str]] = None
    for candidate in _load_users():
        if candidate.get("username") == body.username:
            user = candidate
            break

    # Comparaison bcrypt en temps constant ; compte inexistant -> même chemin
    if user is None or not security.verify_password(
        body.password, user["hashed_password"]
    ):
        # Compté même pour un compte inexistant (pas de divulgation)
        security.register_login_failure(body.username)
        security.audit(body.username, "inconnu", "/auth/login", _content_length(request), HTTP_401_UNAUTHORIZED)
        return JSONResponse(
            status_code=HTTP_401_UNAUTHORIZED,
            content={"detail": security.GENERIC_LOGIN_ERROR},
        )

    # Rôle du compte : valeur contrôlée de users.json (Rôle du contrat)
    role: Role = cast(Role, user["role"])
    security.clear_login_failures(body.username)
    token: str = security.create_access_token(body.username, role, JWT_SECRET)
    security.audit(body.username, role, "/auth/login", _content_length(request), 200)
    return TokenResponse(
        access_token=token,
        expires_in=security.JWT_EXPIRE_MINUTES * 60,
        role=role,
    )


# ---------------------------------------------------------------------------
# POST /search — recherche pondérée (JWT)
# ---------------------------------------------------------------------------

@app.post("/search", response_model=SearchResult)
@limiter.limit("30/minute")
def search(
    request: Request,
    body: SearchRequest,
    user: dict[str, str] = Depends(security.get_current_user),
) -> Any:
    """Recherche : retrieve (rôle du token, subject tel quel) -> extract_claims
    -> build_tree. Le rôle du JWT prime : un employee ne voit jamais un
    document payroll_expert, même si le corps demandait autre chose."""
    documents: list[Document] = pipeline.retrieve(
        query=body.query,
        country=body.country,
        role=user["role"],          # rôle du token, transmis tel quel
        subject=body.subject,       # subject transmis tel quel
    )
    claims = pipeline.extract_claims(documents, body.query)
    result: SearchResult = pipeline.build_tree(
        claims, documents, pipeline.load_experts(), body.weights
    )
    security.audit(user["username"], user["role"], "/search", _content_length(request), 200)
    return result


# ---------------------------------------------------------------------------
# POST /analyze-text — analyse d'un texte libre (JWT)
# ---------------------------------------------------------------------------

@app.post("/analyze-text", response_model=SearchResult)
@limiter.limit("10/minute")
def analyze_text(
    request: Request,
    body: AnalyzeTextRequest,
    user: dict[str, str] = Depends(security.get_current_user),
) -> Any:
    """Analyse un texte libre (ex. email collé) sans le stocker ni le logger.

    Étapes : masquage PII (security.mask_pii, même fonction que claims.py) ->
    détection d'injection (pipeline.detect_injection) -> Document temporaire
    (expert_note, owner null, pays demandé) -> extract_claims -> build_tree.
    Le texte original n'est JAMAIS persisté ni journalisé en entier.
    """
    masked: str = security.mask_pii(body.text)
    suspicious: bool = pipeline.detect_injection(masked)

    # Document temporaire : jamais stocké, jamais écrit sur disque
    temp_doc: Document = Document(
        id="temp-analysis",
        title="Texte soumis pour analyse",
        content=masked,
        source_type="expert_note",
        owner=None,
        country=body.country,
        last_updated=datetime.now(timezone.utc).isoformat(),
        copy_of=None,
        claim="Texte fourni par l'utilisateur (analyse à la volée).",
        claim_quote=masked[:120],
        normalized_value="texte_utilisateur",
        access_level="employee",
        expert_validated=False,
        review_due=None,
    )
    claims = pipeline.extract_claims([temp_doc], "")
    result: SearchResult = pipeline.build_tree(claims, [temp_doc], pipeline.load_experts())
    if suspicious:
        result.warnings.insert(
            0,
            "Le texte soumis contient des instructions suspectes "
            "(tentative d'injection de prompt).",
        )
    security.audit(user["username"], user["role"], "/analyze-text", _content_length(request), 200)
    return result


# ---------------------------------------------------------------------------
# POST /feedback — vote en mémoire (JWT)
# ---------------------------------------------------------------------------

@app.post("/feedback")
@limiter.limit("30/minute")
def feedback(
    request: Request,
    body: FeedbackRequest,
    user: dict[str, str] = Depends(security.get_current_user),
) -> Any:
    """Enregistre un vote (utile/incorrect) : un seul par (username, doc_id).

    Le vote ne modifie JAMAIS le score d'un document. Seul un payroll_expert
    peut faire passer expert_validated à True (état en mémoire, PoC).
    """
    key: tuple[str, str] = (user["username"], body.doc_id)
    if key in _feedback_votes:
        return JSONResponse(
            status_code=HTTP_409_CONFLICT,
            content={"detail": "Vous avez déjà voté pour ce document."},
        )
    _feedback_votes.add(key)

    # Validation expert : réservée au rôle payroll_expert
    role: Role = user["role"]  # type: ignore[assignment]
    if role == "payroll_expert" and body.vote == "useful":
        _expert_validations[body.doc_id] = True

    security.audit(user["username"], user["role"], "/feedback", _content_length(request), 200)
    return {
        "message": "Feedback enregistré.",
        "vote": body.vote,
        "doc_id": body.doc_id,
        # État de validation en mémoire (jamais le score)
        "expert_validated": _expert_validations.get(body.doc_id, False),
    }
