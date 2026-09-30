"""
Sécurité Axe C — un module, fonctions réutilisables.

Contenu :
1.  Config : JWT_SECRET obligatoire (>= 32 caractères), sinon démarrage refusé
2.  JWT HS256 via python-jose, expiration 30 min, claims sub + role
3.  Mots de passe bcrypt, comparaison en temps constant, message générique,
    verrouillage temporaire 5 minutes après 5 échecs par utilisateur
4.  Dépendances FastAPI : get_current_user (401) et require_role
5.  Middleware d'en-têtes de sécurité (CSP, nosniff, DENY, no-referrer, HSTS)
6.  Middleware de limite de taille de corps (20 Ko -> 413)
7.  Handler global d'exceptions : message générique + ID de corrélation
8.  Logging : jamais de secret ni de contenu de requête ; journal d'audit
9.  Masquage PII (email, IBAN, téléphone, registre national belge)
    -> EXPORTÉ : claims.py (axe A) l'importe
10. STATELESS (Cloud Run) : verrouillages en mémoire, voir SECURITY.md

En production, JWT_SECRET est injecté par Secret Manager via la config
Cloud Run (rôle DevOps) : Secret Manager -> variable d'env -> code, jamais
de secret dans le repo.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from starlette.datastructures import MutableHeaders

from backend.models import Role

# ---------------------------------------------------------------------------
# Constantes de sécurité
# ---------------------------------------------------------------------------

JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_MINUTES: int = 30                      # contrat : 1800 secondes
JWT_MIN_SECRET_LEN: int = 32                      # démarrage refusé en dessous
BODY_MAX_BYTES: int = 20 * 1024                   # 20 Ko -> 413 au-delà
LOCKOUT_THRESHOLD: int = 5                        # échecs avant verrouillage
LOCKOUT_MINUTES: int = 5                          # durée du verrouillage
FAILURE_WINDOW_MINUTES: int = 15                  # fenêtre de comptage des échecs

# Message générique unique : ne divulge pas l'existence du compte
GENERIC_LOGIN_ERROR: str = "Identifiants invalides"
GENERIC_LOCKED_ERROR: str = "Trop de tentatives. Réessayez plus tard."

# Hiérarchie des rôles : employee < hr < payroll_expert
ROLE_ORDER: dict[str, int] = {"employee": 0, "hr": 1, "payroll_expert": 2}

# Logger applicatif : jamais de mot de passe, token, clé API ni corps de requête
logger: logging.Logger = logging.getLogger("backend.security")
# Logger d'audit : horodatage, utilisateur, rôle, endpoint, longueur, statut
audit_logger: logging.Logger = logging.getLogger("backend.audit")


# ---------------------------------------------------------------------------
# 1. Configuration : secret JWT validé au démarrage
# ---------------------------------------------------------------------------

def validate_runtime_config(jwt_secret: Optional[str]) -> str:
    """Valide JWT_SECRET au démarrage ; refuse de démarrer s'il est invaliable.

    Appelé par main.py au démarrage (et par les tests avec un secret factice).
    En prod, la valeur vient de Secret Manager via la config Cloud Run.
    """
    if jwt_secret is None or not jwt_secret.strip():
        raise RuntimeError(
            "JWT_SECRET manquant : définissez la variable d'environnement "
            "JWT_SECRET (>= 32 caractères). En production, injectez-la via "
            "Secret Manager (config Cloud Run), jamais dans le repo."
        )
    if len(jwt_secret.strip()) < JWT_MIN_SECRET_LEN:
        raise RuntimeError(
            f"JWT_SECRET trop court ({len(jwt_secret.strip())} caractères) : "
            f"minimum requis {JWT_MIN_SECRET_LEN}."
        )
    return jwt_secret.strip()


# ---------------------------------------------------------------------------
# 2. JWT : création et vérification (HS256, 30 min, claims sub + role)
# ---------------------------------------------------------------------------

def create_access_token(username: str, role: str, secret: str) -> str:
    """Crée un JWT HS256 avec claims sub (utilisateur) et role, valable 30 min."""
    now: datetime = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret: str) -> dict[str, Any]:
    """Décode et vérifie le JWT ; lève JWTError si invalide ou expiré."""
    return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])


# ---------------------------------------------------------------------------
# 3. Mots de passe : bcrypt + verrouillage temporaire en mémoire
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Hache un mot de passe en bcrypt (utilisée pour générer users.json)."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Compare en temps constant ; ne lève jamais (retourne False si format invalide)."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# État en mémoire (STATELESS, PoC) : {username: [dates d'échec]}
# Limite documentée dans SECURITY.md : chaque instance Cloud Run a son propre
# compteur ; en production, externaliser dans Redis.
_login_failures: dict[str, list[datetime]] = {}
_lockouts: dict[str, datetime] = {}


def _prune_failures(username: str, now: datetime) -> list[datetime]:
    """Supprime les échecs hors fenêtre de comptage."""
    window_start: datetime = now - timedelta(minutes=FAILURE_WINDOW_MINUTES)
    kept: list[datetime] = [
        d for d in _login_failures.get(username, []) if d >= window_start
    ]
    _login_failures[username] = kept
    return kept


def is_locked_out(username: str) -> bool:
    """True si l'utilisateur est verrouillé (compte existant ou non : pas de divulgation)."""
    now: datetime = datetime.now(timezone.utc)
    locked_until: Optional[datetime] = _lockouts.get(username)
    if locked_until is not None:
        if now < locked_until:
            return True
        # Verrouillage expiré : nettoyage
        del _lockouts[username]
        _login_failures.pop(username, None)
    return False


def register_login_failure(username: str) -> None:
    """Enregistre un échec ; verrouille 5 minutes au 5e échec dans la fenêtre."""
    now: datetime = datetime.now(timezone.utc)
    kept: list[datetime] = _prune_failures(username, now)
    kept.append(now)
    if len(kept) >= LOCKOUT_THRESHOLD:
        _lockouts[username] = now + timedelta(minutes=LOCKOUT_MINUTES)
        # Le verrouillage compte les échecs, y compris pour des comptes inexistants
        # (aucune divulgation de l'existence du compte).
        audit_logger.info(
            "evenement=verrouillage utilisateur=MASQUE "
            "duree_minutes=%d", LOCKOUT_MINUTES
        )


def clear_login_failures(username: str) -> None:
    """Réinitialise les échecs après une connexion réussie."""
    _login_failures.pop(username, None)
    _lockouts.pop(username, None)


def reset_login_state() -> None:
    """Réinitialise tout l'état de verrouillage (réservé aux tests)."""
    _login_failures.clear()
    _lockouts.clear()


# ---------------------------------------------------------------------------
# 4. Dépendances FastAPI : get_current_user et require_role
# ---------------------------------------------------------------------------

_bearer_scheme: HTTPBearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict[str, str]:
    """Extrait le JWT de l'en-tête Authorization ; 401 si absent/invalide/expiré.

    Le secret est lu via app.state.jwt_secret (validé au démarrage).
    Retourne {"username": ..., "role": ...}.
    """
    secret: str = request.app.state.jwt_secret
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload: dict[str, Any] = decode_access_token(credentials.credentials, secret)
    except JWTError:
        # Invalide OU expiré : même message, pas d'information exploitable
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username: Optional[Any] = payload.get("sub")
    role: Optional[Any] = payload.get("role")
    if not isinstance(username, str) or not isinstance(role, str) or role not in ROLE_ORDER:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"username": username, "role": role}


def require_role(minimum: Role):
    """Dépendance factory : exige un rôle minimum (employee < hr < payroll_expert)."""

    def _dependency(user: dict[str, str] = Depends(get_current_user)) -> dict[str, str]:
        if ROLE_ORDER.get(user["role"], -1) < ROLE_ORDER[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Privilèges insuffisants",
            )
        return user

    return _dependency


# ---------------------------------------------------------------------------
# 5. Middleware d'en-têtes de sécurité
# ---------------------------------------------------------------------------

class SecurityHeadersMiddleware:
    """Ajoute les en-têtes de sécurité à chaque réponse.

    - CSP : connect-src inclut 'self', le backend local et l'URL publique
      du backend (BACKEND_PUBLIC_URL) si elle est configurée.
    - Cache-Control: no-store sur les réponses aux requêtes authentifiées
      (présence d'un en-tête Authorization), pour ne jamais mettre en cache
      de données personnelles.
    """

    def __init__(self, app, backend_public_url: Optional[str] = None) -> None:
        self.app = app
        self.backend_public_url = (
            backend_public_url.strip() if backend_public_url else None
        )

    def _csp(self) -> str:
        connect_src: str = "connect-src 'self' http://localhost:8000"
        if self.backend_public_url:
            connect_src += f" {self.backend_public_url}"
        return f"default-src 'self'; {connect_src}"

    async def __call__(self, scope: dict, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains"
                )
                headers["Content-Security-Policy"] = self._csp()
                # no-store pour toute requête portant un token (données perso)
                req_headers: dict[bytes, bytes] = {
                    k.lower(): v for k, v in scope.get("headers", [])
                }
                if b"authorization" in req_headers:
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_headers)


# ---------------------------------------------------------------------------
# 6. Middleware de limite de taille de corps (20 Ko -> 413)
# ---------------------------------------------------------------------------

class BodySizeLimitMiddleware:
    """Rejette les requêtes avec un corps > 20 Ko (Content-Length), code 413.

    Réponse générique, sans détail interne. Les requêtes sans Content-Length
    (chunked) sont bornées par la validation Pydantic des schémas (max_length).
    """

    def __init__(self, app, max_bytes: int = BODY_MAX_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: dict, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers: dict[bytes, bytes] = {
            k.lower(): v for k, v in scope.get("headers", [])
        }
        content_length: Optional[bytes] = headers.get(b"content-length")
        if content_length is not None:
            try:
                length: int = int(content_length)
            except ValueError:
                length = -1
            if length > self.max_bytes:
                response: JSONResponse = JSONResponse(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    content={"detail": "Corps de requête trop volumineux"},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# 7. Handler global d'exceptions : générique + ID de corrélation
# ---------------------------------------------------------------------------

async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Toute exception non gérée -> 500 générique avec ID de corrélation.

    Aucune stack trace ni détail interne dans la réponse ; le détail complet
    (traceback + ID) part dans les logs serveur uniquement.
    """
    correlation_id: str = uuid.uuid4().hex[:12]
    logger.exception("Erreur non gérée correlation_id=%s path=%s", correlation_id, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Une erreur interne est survenue. "
                      f"Référence : {correlation_id}"
        },
    )


# ---------------------------------------------------------------------------
# 8. Audit : journal sans secret, sans contenu de requête
# ---------------------------------------------------------------------------

# Patterns que le logger ne doit JAMAIS laisser passer (défense en profondeur)
_SECRET_SCRUB_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?:password|motdepasse|mot_de_passe|secret|api_key|apikey|token)\"\s*:\s*\"[^\"]*\"", re.IGNORECASE), "[REDACTÉ]"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+"), r"\1[REDACTÉ]"),
]


def scrub_secrets(text: str) -> str:
    """Retire les mots de passe / tokens / clés d'un texte destiné aux logs."""
    scrubbed: str = text
    for pattern, replacement in _SECRET_SCRUB_PATTERNS:
        scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed


def audit(
    username: str,
    role: str,
    endpoint: str,
    content_length: int,
    status_code: int,
) -> None:
    """Journal d'audit : horodatage, utilisateur, rôle, endpoint, longueur, statut.

    Jamais de corps de requête, jamais de token ni de mot de passe :
    seuls les métadonnées ci-dessus sont journalisées.
    """
    safe_user: str = scrub_secrets(username)
    audit_logger.info(
        "audit utilisateur=%s role=%s endpoint=%s longueur=%d statut=%d",
        safe_user, role, endpoint, content_length, status_code,
    )


# ---------------------------------------------------------------------------
# 9. Masquage PII — EXPORTÉ pour claims.py (axe A)
# ---------------------------------------------------------------------------

_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Adresse email
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[EMAIL MASQUÉ]"),
    # IBAN belge : BE## #### #### #### (espaces optionnels)
    (re.compile(r"BE\d{2}[ ]?\d{4}[ ]?\d{4}[ ]?\d{4}", re.IGNORECASE), "[IBAN MASQUÉ]"),
    # Téléphone belge : +32 2 345 67 89 ou 02 345 67 89 ou 0475 12 34 56
    (re.compile(r"(?:\+32[ .-]?\d{1,3}|0\d)[ .-]?\d{2}[ .-]?\d{2}[ .-]?\d{2}(?:[ .-]?\d{2})?"), "[TÉLÉPHONE MASQUÉ]"),
    # Numéro de registre national belge : YY.MM.DD-123.45 ou YY.MM.DD.123.45
    (re.compile(r"\d{2}[.-]\d{2}[.-]\d{2}[-.]?\d{3}[.-]\d{2}"), "[REGISTRE NATIONAL MASQUÉ]"),
]


def mask_pii(text: str) -> str:
    """Masque les PII (email, IBAN, téléphone, registre national belge).

    Fonction EXPORTÉE : claims.py (axe A) l'importe et l'applique aux
    contenus avant analyse. Même comportement des deux côtés.
    """
    masked: str = text
    for pattern, replacement in _PII_PATTERNS:
        masked = pattern.sub(replacement, masked)
    return masked
