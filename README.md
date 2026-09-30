# Payroll Policies — PoC hackathon

> NOTE (axe C) : ce README est créé par l'axe B. Ma seule contribution est la
> section « Démo et mots de passe » ci-dessous — axe B, ne la supprimez pas.

## Démo et mots de passe

Le backend tourne en local sur http://localhost:8000 (voir SECURITY.md pour
l'installation complète : venv, `pip install -r requirements.txt`, `.env`
copié depuis `.env.example` avec `JWT_SECRET` renseigné, puis
`uvicorn backend.main:app --reload`).

Trois comptes de démonstration (fictifs, hashs bcrypt dans
`backend/data/users.json`) :

| Utilisateur | Rôle | Mot de passe |
|---|---|---|
| `alice` | employee | `Alice!Demo2026` |
| `bob` | hr | `Bob!Demo2026` |
| `chloe` | payroll_expert | `Chloe!Demo2026` |

Scénario de démo :

1. `POST /auth/login` avec alice → JWT valable 30 minutes.
2. `POST /search` (`{"query": "duree de preavis travailleur", "country": "BE", "subject": "worker"}`) → réponse `confident`, le préavis de 3 mois, sources pondérées, doublon replié.
3. Même requête avec chloe → le document confidentiel `doc-be-004` (grille salariale) apparaît pour le rôle payroll_expert uniquement.
4. `POST /analyze-text` avec un email collé contenant des PII et une tentative d'injection → PII masquées, tentative détectée et signalée, sans influence sur la réponse.
5. Faites 6 erreurs de mot de passe pour alice → verrouillage 5 minutes (429).

Aucune donnée réelle : documents, experts et comptes sont fictifs.
