# Lot 0 — Bloc 6 : tests backend

## Configuration (`pyproject.toml`)
- `asyncio_mode = "auto"`.
- `asyncio_default_fixture_loop_scope = "session"` et `asyncio_default_test_loop_scope = "session"` : **une seule boucle** partagée par le client et les tests (évite les erreurs « attached to a different loop »).
- `addopts = "-ra --strict-markers --cov=app --cov-branch --cov-report=term-missing"`.
- Marqueurs : `unit`, `integration`, `property`, `concurrency`, `architecture`, `slow`.
- Couverture : seuil global de **85 %** au lot 0 ; **100 %** sur `vote_engine` et `anonymity` à partir du lot 2, avec un contrôle par module.
- Hypothesis : profil `ci` (`max_examples=500`, `deadline=None`) et profil `dev` (`max_examples=50`), choisis par `HYPOTHESIS_PROFILE`.

## Infrastructure (`tests/conftest.py`)
- **MongoDB réel en réplica set**. Pas de `mongomock` : les validateurs, les index, les transactions et les TTL doivent être réellement exercés.
- **Une base par module de test** (`abaque_test_<uuid court>`), migrations appliquées, supprimée en fin de module. Entre deux tests : `delete_many({})` sur toutes les collections.
- Secrets de test : générés par session (trois valeurs distinctes), injectés dans `Settings`, avec vidage du cache de `get_settings`.
- Fixtures :
  - `client` : un `AsyncMongoClient` par session ;
  - `app` : `create_app()` avec le `lifespan` ;
  - `http` : `httpx.AsyncClient(transport=ASGITransport(app))` avec cookies ;
  - `org_a` et `org_b` ;
  - `login_as(admin)` : client authentifié, cookies et en-tête CSRF posés ;
  - `capture_logs`.
- `tests/factories.py` : documents **valides selon les schémas** pour **toutes** les collections, y compris le domaine vote.

## Organisation
> **Réalisé (D032)** : arborescence par domaine (`core`, `db`, `entitlements`, `repositories`, `api`, `app`, `architecture`, `property`) plutôt que par type ; support HTTP partagé dans `tests/api_support.py`.

```
tests/
├── conftest.py   factories.py
├── unit/            config, password_policy, jwt, entitlements, log_redaction, rate_limiter,
│                    identity (normalize_email, fingerprint)
├── integration/     migrations, schemas_validators, repositories_tenancy, sessions,
│                    auth_tokens, auth_api, organization_api, health, startup
├── concurrency/     refresh_rotation, auth_token_consume, transaction_retry (failCommand)
├── architecture/    imports, routes_tenancy, openapi_contract
└── property/        (prêt pour le lot 2)
```

## Tests d'architecture
- **`test_imports.py`** (analyse par AST, y compris les imports dans les fonctions) :
  - `motor` interdit partout ;
  - `pymongo` et `bson` seulement dans `app/repositories/` et `app/db/` ;
  - `app/vote_engine`, `app/anonymity` et `app/entitlements` n'importent ni `pymongo`, ni `bson`, ni `fastapi`, ni `app.db`, ni `app.repositories` ;
  - `app/repositories/platform/` n'importe pas les repositories des domaines vote et identité ;
  - `BallotReader` n'est importé que depuis `app/anonymity`, `app/services/restitution` et `app/services/export` ;
  - aucun fichier de `frontend/src` n'importe un chemin `backend`.

  Le message d'échec nomme le fichier, la ligne et la règle.
- **`test_routes_tenancy.py`** : test d'isolation **paramétré automatiquement**.
  1. Parcourir `app.routes`, inspecter l'arbre de dépendances et retenir toutes les routes qui dépendent de `current_org`.
  2. Pour chaque route et méthode, appeler avec la session de B sur une ressource de A (registre `RESOURCE_FACTORIES`) → **404** attendu.
  3. Une route sans usine déclarée **fait échouer le test** (« ajoute une usine pour tester l'isolation de cette route »).
- **`test_openapi_contract.py`** : `create_app()` s'importe et produit l'OpenAPI sans MongoDB ; chaque route déclare au moins une réponse d'erreur.

## Tests à livrer au lot 0
- **Unitaires** :
  - `Settings` ;
  - politique de mot de passe ;
  - JWT ;
  - `entitlements` ;
  - masquage des journaux (chaque clé, chaque motif) ;
  - limite de débit.
- **Intégration** :
  - migrations idempotentes et index en conflit ;
  - **validateurs en test paramétré sur `ALL_SCHEMAS`** : un document de l'usine est accepté, le même document avec un champ supplémentaire est rejeté par MongoDB ;
  - champs interdits, formats de date et UUID du domaine vote ;
  - `anonymity_threshold < 3` → rejeté ;
  - repositories ;
  - API d'authentification ;
  - démarrage.
- **Concurrence** (`asyncio.gather`, 20 appels) : rotation du refresh token et consommation de `auth_tokens` → un seul succès.
- **`run_in_transaction`** (fixture `fail_point` qui active puis désactive `configureFailPoint` ; `mongod` lancé avec `enableTestCommands=1`) :
  - `TransientTransactionError` sur `insert` → callback exécuté deux fois, un seul document ;
  - `UnknownTransactionCommitResult` sur `commitTransaction` → callback exécuté **une fois**, un seul document ;
  - erreur métier → rien n'est écrit.
- **Validateurs en profondeur** : pour chaque collection, un champ supplémentaire à la racine, dans un sous-objet et dans un élément de tableau est rejeté par MongoDB.
- **Identité** : tests de `normalize_email` et du fingerprint (voir `vote-transaction.md`).
- **`auth_tokens`** : consommation unique, expiration vérifiée avant le passage du TTL, mauvais `purpose` refusé, nouvelle demande qui invalide l'ancienne.
- **Journaux** : après un parcours complet (inscription, vérification, connexion, rafraîchissement, réinitialisation), aucun mot de passe, jeton, JWT (`eyJ`) ni e-mail en clair.

## Commandes
- `docker compose exec api uv run pytest`
- `docker compose exec api uv run pytest -m "not slow"`
- `docker compose exec api uv run pytest tests/architecture`

Attendu : tout est vert, couverture d'au moins 85 %, aucun test ignoré sans raison écrite.
