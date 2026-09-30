"""
Liaison ADC (Application Default Credentials) — accès Google Cloud.

Aucune clé Google n'est stockée dans le repo ni dans .env : l'identité vient
de ADC, résolue par google.auth.default() dans cet ordre :
    1. GOOGLE_APPLICATION_CREDENTIALS (compte de service JSON, CI/tests)
    2. %APPDATA%/gcloud/application_default_credentials.json
       (local : gcloud auth application-default login)
    3. Métadonnées du service Cloud Run (prod : compte de service attaché,
       rien à faire côté code)
    4. Workload Identity Federation (CI GitHub : jetons OIDC éphémères)

Fonction exportée : get_adc_credentials() -> (credentials, project_id)
Utilisée par claims.py (axe A) pour tout appel Google Cloud (Vertex, etc.).
L'API fonctionne SANS ADC tant que USE_STUBS=true : la liaison est informative
au démarrage, jamais bloquante.
"""

from __future__ import annotations

import logging
from typing import Optional

import google.auth
from google.auth import exceptions as gauth_exceptions
from google.auth.credentials import Credentials

logger: logging.Logger = logging.getLogger("backend.gcp")


class GoogleCloudADCError(RuntimeError):
    """ADC absent : porte des instructions de liaison en français."""

    def __init__(self) -> None:
        super().__init__(
            "Aucun identifiant Google Cloud (ADC) trouvé.\n"
            "Pour relier ADC :\n"
            "  - local   : gcloud auth application-default login\n"
            "  - CI      : Workload Identity Federation (OIDC GitHub -> GCP)\n"
            "  - prod    : compte de service attache au service Cloud Run\n"
            "Aucune cle ne doit etre stockee dans le repo ni dans .env."
        )


def get_adc_credentials() -> tuple[Credentials, Optional[str]]:
    """Résout l'identité ADC et le project ID ; jamais de secret en retour.

    Lève GoogleCloudADCError (instructions incluses) si ADC n'est pas relié.
    Le project ID n'est pas un secret : il peut être journalisé.
    """
    try:
        credentials: Credentials
        project: Optional[str]
        credentials, project = google.auth.default()
    except gauth_exceptions.DefaultCredentialsError as exc:
        raise GoogleCloudADCError() from exc
    return credentials, project
