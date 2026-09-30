# SECURITY.md — Axe C « API & Sécurité »

Documentation de sécurité du backend : modèle de menaces, mesures, tests,
risques résiduels et trajectoire production. Ce document fait partie des
livrables notés (10 % de la note porte sur la sécurité, visible et testée).

## 1. Démarrage rapide

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows (Linux : source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env        # Linux : cp
# renseignez JWT_SECRET (>= 32 caractères) dans .env
uvicorn backend.main:app --reload   # http://localhost:8000
pytest backend/tests/test_security.py
```

Le démarrage est **refusé** si `JWT_SECRET` est absent ou fait moins de
32 caractères (`backend/security.py::validate_runtime_config`, testé).

## 2. Comptes de démonstration

Trois comptes fictifs dans `backend/data/users.json` (hashs bcrypt uniquement,
jamais de mot de passe en clair dans le repo) :

| Utilisateur | Rôle | Mot de passe de démo |
|---|---|---|
| `alice` | employee | `Alice!Demo2026` |
| `bob` | hr | `Bob!Demo2026` |
| `chloe` | payroll_expert | `Chloe!Demo2026` |

Comptes et mots de passe de démonstration, sans aucune donnée réelle.
En production : SSO et rotation des secrets (voir §6).

## 3. Modèle de menaces simplifié

| Menace | Mesure | Où (fichier) | Test |
|---|---|---|---|
| **Injection de prompt** (document piégé qui tente de détourner l'analyse) | Détection de patterns d'injection ; le claim piégé garde `suspicious=true` mais score 0 et zéro influence sur la réponse ; avertissement FR explicite ; branches toutes visibles (conflit jamais caché) | `backend/stubs.py` (`INJECTION_PATTERNS`, `detect_injection`, `build_tree`), axe A (`claims.py`) au merge | (h) |
| **XSS** | En-têtes `Content-Security-Policy` (`default-src 'self'`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` ; JSON uniquement ; pas de rendu HTML | `backend/security.py::SecurityHeadersMiddleware` | (m) |
| **Fuite de données** (PII, rôle, cache) | Masquage PII (email, IBAN BE, téléphone, registre national belge) sur `/analyze-text` et exporté vers claims.py ; filtrage par rôle du JWT dans `retrieve` (un employee ne voit jamais un document payroll_expert) ; `Cache-Control: no-store` sur toute réponse authentifiée ; texte analysé jamais persisté ni logué | `backend/security.py::mask_pii`, `backend/main.py` (endpoints), `backend/stubs.py::retrieve` | (c), (k), (m) |
| **Brute force** (login) | bcrypt + comparaison en temps constant ; message générique unique « Identifiants invalides » (pas de divulgation de l'existence du compte) ; verrouillage 5 min après 5 échecs par utilisateur (429 générique) ; rate limit `/auth/login` 5/min/IP | `backend/security.py` (§3), `backend/main.py::login` | (g1), (g2) |
| **Accès non autorisé** (élévation de rôle) | JWT HS256 signé, expiration 30 min, claims `sub`+`role` ; 401 uniforme absent/invalide/expiré ; rôle pris du token, jamais du corps ; validation expert réservée à `payroll_expert` ; CORS restreint à `FRONTEND_ORIGIN` (jamais `*`), méthodes GET/POST | `backend/security.py` (§2, §4), `backend/main.py` | (a), (b), (l), (o) |
| **Déni de service applicatif** | Rate limiting slowapi : `/search` 30/min/IP, `/auth/login` 5/min/IP, `/analyze-text` 10/min/IP ; corps limité à 20 Ko (413) ; `max_length` Pydantic partout | `backend/main.py` (limiter), `backend/security.py::BodySizeLimitMiddleware` | (g1), (i), (p) |
| **Fuite d'information en erreur** | Handler global d'exceptions : 500 générique + ID de corrélation, traceback en logs serveur uniquement ; 422 sans jamais renvoyer la valeur saisie | `backend/security.py::generic_exception_handler`, `backend/main.py::validation_error_handler` | (d), (j) |
| **Fuite dans les logs** | Journal d'audit limité aux métadonnées (horodatage, utilisateur, rôle, endpoint, longueur, statut) ; jamais de corps de requête, mot de passe, token ou clé API ; `scrub_secrets` en défense en profondeur | `backend/security.py` (§8) | (n) |
| **Chaîne d'approvisionnement** | Dépendances épinglées dans `requirements.txt` ; audit : voir §5 | `requirements.txt` | pip-audit |

## 4. Bascule USE_STUBS

`USE_STUBS` (défaut `true`) : `backend/main.py` utilise `backend/stubs.py`
(6 documents fictifs en dur, mêmes signatures que le contrat). Avec
`USE_STUBS=false`, main.py importe `backend.claims.py` (axe A), qui doit
exporter : `load_documents`, `load_experts`, `retrieve`, `extract_claims`,
`detect_injection`, `build_tree`. **Aucun code à retirer après le merge** :
la bascule est une variable d'environnement, les signatures sont identiques.

## 5. Audit de la chaîne d'approvisionnement

```bash
pip install pip-audit
pip-audit -r requirements.txt

npm audit          # côté frontend (axe B) — 0 vulnérabilité attendue
```

Exécuter avant chaque déploiement et dans le workflow CI (rôle DevOps).

**Résultat au 2026-09-30** (dernière exécution, axe C) :

| Paquet | Advisory | Statut |
|---|---|---|
| starlette < 0.47 | PYSEC-2026-1941/1942/2280/2281 | **Corrigé** : épingle starlette 1.7.0 (via fastapi 0.142.2) |
| python-jose 3.3.0 | PYSEC-2024-233 | **Corrigé** : épingle 3.4.0 |
| pytest 8.3.4 | PYSEC-2026-1845 | **Corrigé** : épingle 9.0.3 |
| pyasn1 0.4.8 (transitif de python-jose) | PYSEC-2026-3455/3456/3457 | **Résiduel assumé** : le fix (0.6.4) est bloqué par l'épingle `pyasn1<0.5.0` de python-jose, imposé par le contrat. Pile RSA/ECDSA non utilisée : uniquement HS256, algorithmes épinglés dans `security.py` |
| ecdsa 0.19.2 (transitif de python-jose) | PYSEC-2026-1325 | **Résiduel assumé** : pas de correctif publié ; même mitigation (HS256 uniquement) |

## 6. Risques résiduels (assumés pour le PoC) et trajectoire production

| Risque résiduel | Impact | Ce qu'on ferait en production |
|---|---|---|
| Verrouillage login **en mémoire** | Chaque instance Cloud Run a son propre compteur : le seuil effectif peut atteindre 5 x N instances | Externaliser dans Redis (ou stockage Cloud) |
| Feedback **en mémoire** | Votes non partagés entre instances ; perdus au redémarrage | Table dédiée + contrainte d'unicité (user, doc) |
| Rate limiting par IP « vue » | Derrière le load balancer Cloud Run, l'IP vue peut être celle du LB (limites déclenchées collectivement ou contournées) | Utiliser l'IP réelle des en-têtes forwarded + quotas par compte, ou un WAF |
| Différence de temps bcrypt | Un login sur compte inexistant répond plus vite (pas de hash) → énumération possible en théorie | Hash factice sur comptes inexistants |
| Advisories résiduels python-jose (pyasn1, ecdsa) | Pile RSA/ECDSA de python-jose, non utilisée (HS256 uniquement) | Migrer vers PyJWT ou une lib JOSE maintenue dès que le contrat le permet |
| JWT HS256 symétrique | Le secret signe ET vérifie côté API | RS256/Keycloak, SSO entreprise (OIDC) |
| Pas de chiffrement au repos géré par l'app | Les données du PoC sont fictives | Chiffrement au repos (Cloud SQL/Secret Manager), RGPD (minimisation, rétention, registre des traitements) |
| Pas d'audit externe | — | Pentest externe avant mise en production |

## 7. Flux des secrets

```
Secret Manager (créé par le DevOps)
        │  (config Cloud Run : variable d'env)
        ▼
Processus API (JWT_SECRET, ANTHROPIC_API_KEY)
        ▼
Code (os.getenv — jamais de valeur en dur)
```

Jamais de secret dans le repo : `.env` est ignoré (`.gitignore`),
`.env.example` documente les variables sans valeur sensible.

**Accès Google Cloud via ADC** (Application Default Credentials, pas de clé
API) : aucune clé dans le repo ni dans `.env`. En local, `gcloud auth
application-default login` écrit les identifiants hors du repo
(`%APPDATA%\gcloud\application_default_credentials.json`) ; en production,
c'est le compte de service attaché au service Cloud Run (rôle DevOps) qui
fait foi — les bibliothèques `google-cloud` les trouvent automatiquement.
Le `.gitignore` ignore en plus `service-account*.json`, `*-sa-key*.json` et
`gcp-*.json` par précaution.

## 8. Surface de test

`backend/tests/test_security.py` — 19 tests (18 cas du contrat (a) à (q),
g scindé en g1/g2, + 1 complément config), pytest + TestClient,
**aucun appel réseau réel**. Dernière exécution : 19/19 passés.
