# Contrat API consommé par le frontend

Base URL locale : `http://localhost:8000` (modifiable avec `VITE_API_URL`). Tous les corps et réponses sont en JSON UTF-8. Sauf pour le login et le health check, les routes attendent `Authorization: Bearer <access_token>`. Les erreurs ne doivent pas exposer de détails techniques à l’écran.

## `POST /auth/login`

Requête :

```json
{"username":"utilisateur","password":"mot-de-passe"}
```

Réponse `200` :

```json
{"access_token":"<jeton>","token_type":"bearer","expires_in":1800,"role":"employee"}
```

`role` vaut `employee`, `hr` ou `payroll_expert`. Le frontend garde le jeton uniquement dans la mémoire du module API. Les réponses d’identifiants invalides ou de verrouillage doivent rester génériques.

## `POST /search`

Requête authentifiée :

```json
{
  "query":"Comment sont remboursés les frais de transport ?",
  "country":"BE",
  "subject":"worker",
  "weights":{"freshness":0.3,"authority":0.25,"owner":0.2,"country":0.25}
}
```

`query` fait 3 à 300 caractères, `country` vaut `BE`, `FR` ou `NL`, `subject` vaut `worker` ou `group`. `weights` est facultatif ; chacune de ses quatre valeurs est dans `[0,1]`.

## `POST /analyze-text`

Requête authentifiée : `{"text":"…","country":"BE"}`. Le texte fait 20 à 5 000 caractères. La réponse utilise le même format `SearchResult` que `/search`.

## Format `SearchResult`

```json
{
  "status":"conflict",
  "answer":null,
  "confidence":40.57,
  "branches":[
    {
      "value":"preavis_3_mois",
      "claim_text":"Le préavis applicable est de trois mois.",
      "score":0.71,
      "share":40.57,
      "sources":[
        {
          "doc_id":"POL-BE-014",
          "title":"Politique RH belge — préavis",
          "score":0.71,
          "breakdown":{"freshness":0.5,"authority":1,"owner":0.3,"country":1},
          "is_duplicate":false,
          "quote":"Le délai de préavis applicable est de trois mois.",
          "needs_review":false,
          "suspicious":false,
          "expiring_soon":false
        }
      ]
    }
  ],
  "stats":{"reliable_docs_pct":57.14,"total_docs":7,"reliable_docs":4,"duplicates_collapsed":3},
  "warnings":["Document possiblement d'un autre pays : Procédure française"],
  "suggested_expert":{"name":"Camille Martin","team":"Expertise légale BE"}
}
```

`status` est `confident`, `conflict` ou `low`. `answer` est une chaîne seulement en statut `confident`, sinon `null`. `confidence` et `share` sont des pourcentages de 0 à 100 ; `score` et les quatre valeurs de `breakdown` sont compris entre 0 et 1. Les branches contiennent toutes les versions. `suggested_expert` peut être `null`. Les titres, citations, affirmations et avertissements sont des données non fiables et le frontend les rend comme texte.

## `POST /feedback`

Requête authentifiée : `{"doc_id":"POL-BE-014","vote":"useful"}`. `vote` vaut `useful` ou `wrong`. Réponse : `{"ok":true}`. Le vote n’altère pas le score affiché localement.

## `GET /health`

Sans authentification. Réponse attendue : `{"status":"ok"}`. Le frontend ne l’interroge pas pendant le flux utilisateur.

## Configuration mock

Copier `.env.example` en `.env.local` et conserver `VITE_USE_MOCK=true` pour utiliser les identifiants fictifs et les fixtures locales. Pour le backend local, passer `VITE_USE_MOCK=false` et garder `VITE_API_URL=http://localhost:8000`. Aucun secret ne doit être placé dans une variable `VITE_*` : ces valeurs sont intégrées au bundle navigateur.
