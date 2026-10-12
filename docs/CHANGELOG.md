# Changelog

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/). Une section par lot : livré, ouvert, reporté.

## [Non publié]

### Cadrage (2026-10-12)
- Spécification `docs/PROMPT_MVP.md` figée (SaaS multi-organisations, anonymat, 6 lots).
- Dossier `docs/architecture/` : spécifications détaillées du lot 0 (blocs 1 à 7) et des garanties (transaction de vote, anonymat, exports, tests du lot 2, production).
- `docs/DECISIONS.md` : D001 à D026.
- `docs/adr/0001-stack.md`.

### Lot 0 — Socle (en cours)
- Blocs 1 et 2 produits puis corrigés (types OpenAPI commités, virtualenv hors du volume, nginx avec en-têtes par `location` et proxy `/api`, 1 worker, secrets de CI générés, SHA vérifiés, Dependabot uv avec groupes).
- Bloc 3 : partie a corrigée et validée (sous réserve des ajustements de lint : imports inutilisés, `per-file-ignores`, `noqa` inutile, code de sortie du script de mots de passe) ; partie b à produire. Historique : (voir `docs/architecture/lot0-03-core-db.md`, `lot0-05-auth-api.md` et `vote-transaction.md`). Précisions ajoutées : transactions via `with_transaction` (D024), normalisation des e-mails (D023), schémas `auth_tokens` et `participant_links`, `additionalProperties: false` à chaque niveau.

- **Instantané Git (2026-10-12, branche `lot-0-socle`)** — travail en cours, blocs 1, 2, 3a et 3b partie 1/2 : Docker, Compose, nginx, CI, Dependabot, `pyproject.toml`, `core/` (config, identity, security, logging, middleware), `db/client.py`, `db/schemas/` (21 schémas `$jsonSchema`), liste de mots de passe courants, `scripts/export_openapi.py`, `backend/uv.lock` (81 paquets). D026 ajoutée.
- Manquent encore (bloc 3b partie 2/2 et suivants) : index, migrations, `app/main.py`, seed, repositories, API, tests, `frontend/package.json`. **La CI échoue tant qu'ils n'existent pas** : c'est attendu sur cette branche.

#### Reporté au lot 1
- Activation du job CI `e2e` (premier parcours Playwright : vote anonyme sur viewport mobile).
- Fichiers `docs/samples/items.csv` et `participants.csv`.
