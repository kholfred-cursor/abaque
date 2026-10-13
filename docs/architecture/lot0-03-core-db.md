# Lot 0 — Bloc 3 : backend `core` et `db`

## `backend/pyproject.toml`
- Dépendances : `fastapi`, `uvicorn[standard]`, **`pymongo` sans extras** (pas de `aws` ni de `encryption`, inutiles ici ; `srv` seulement si Atlas est retenu), `pydantic`, `pydantic-settings`, `argon2-cffi`, `PyJWT`, `APScheduler>=3.11,<4`, `email-validator`.
- Dépendances de développement dans **`[dependency-groups] dev = [...]`** (PEP 735). La clé `[tool.uv] dev-dependencies` est dépréciée, et une auto-référence `abaque-backend[dev]` ne fonctionne pas sans système de build.
- `pytest` : `asyncio_mode = "auto"`, `asyncio_default_fixture_loop_scope = "session"`, **`asyncio_default_test_loop_scope = "session"`**, `addopts = "-ra --strict-markers --cov=app --cov-branch"`, et **tous** les marqueurs (`unit`, `integration`, `property`, `concurrency`, `architecture`, `slow`).
- Couverture : **ne pas exclure `app/db/seed.py`**. Il contient le contournement de la politique de mot de passe et le refus en production, et doit donc être testé.
- Ruff : `[tool.ruff.lint.per-file-ignores]` avec `"tests/**" = ["S101", "S105", "S106"]` (les `assert` et les secrets de test sont légitimes) et `"scripts/**" = ["T20"]` (les `print` sont légitimes dans les scripts). Aucun `noqa` pour une règle non activée (RUF100).
- `mypy --strict` avec le plugin `pydantic.mypy`. Ruff avec au minimum `E`, `F`, `I`, `UP`, `B`, `S`, `SIM`, `RUF`.
- Les versions exactes sont figées par `uv.lock`, commité.

## `app/core/config.py` (pydantic-settings)
- `ENVIRONMENT: Literal["development","production"]`.
- Champs :
  - `MONGODB_URI`, `DATABASE_NAME` ;
  - `JWT_SECRET`, `CREDENTIAL_HMAC_KEY` (`SecretStr`, 32 caractères minimum) et `IP_HASH_SALT` (`SecretStr`, 16 minimum) ;
  - `ACCESS_TOKEN_EXPIRE_MINUTES=15`, `REFRESH_TOKEN_EXPIRE_DAYS=14` ;
  - `SEED_DEMO=False`, `COOKIE_SECURE`, `APP_BASE_URL` ;
  - `SIGNUP_ENABLED: bool | None = None`, résolu en `True` en développement et **`False` en production** s'il n'est pas défini explicitement ;
  - `RATE_LIMIT_BACKEND="memory"`, `WEB_CONCURRENCY=1`, `MONGO_SLOWMS`.
- Validateurs de modèle :
  - **refus si deux secrets sont identiques** ;
  - en production : refus si `COOKIE_SECURE` est faux, si `SEED_DEMO` est vrai, ou si `WEB_CONCURRENCY > 1` avec `RATE_LIMIT_BACKEND="memory"` (voir `production.md`) ; `SIGNUP_ENABLED` vaut faux par défaut.
- `credential_key_id` (propriété) : 16 premiers caractères hexadécimaux de `HMAC-SHA256(CREDENTIAL_HMAC_KEY, "abaque-key-id")`.
- `model_config` : **`env_file=None`**. Les variables viennent de l'environnement (Docker `env_file`, CI) ; les tests ne doivent jamais lire le `.env` du développeur.
- En production : refus si `MONGODB_URI` vaut la valeur par défaut de développement.
- `get_settings()` mis en cache. **Aucun accès à la base à l'import** : `create_app()` doit pouvoir être importé sans connexion (export OpenAPI).

## `app/core/logging.py`
- Journalisation JSON structurée.
- **Masquage** :
  - **par sous-chaîne** dans le nom de clé normalisé (minuscules) : `password`, `token`, `refresh`, `access`, `csrf`, `secret`, `email`, `fingerprint`, `authorization`, `cookie`. Ainsi `new_password`, `refresh_token` ou `X-CSRF-Token` sont couverts ;
  - par motif dans les valeurs : e-mail, JWT (`eyJ…`), chaînes hexadécimales de 32 caractères ou plus ;
  - récursif dans les `dict` **et les listes** ;
  - **appliqué aussi au texte des exceptions et des tracebacks**. Un `DuplicateKeyError` de PyMongo contient la valeur en double (`dup key: { credential_fingerprint: "…" }` ou un e-mail) ;
  - horodatage ISO 8601 en UTC.
- Les journaux d'accès sont produits par un **middleware ASGI pur** (et non `BaseHTTPMiddleware`, qui pose des problèmes avec le streaming et les tâches de fond). Il journalise méthode, chemin **sans query string sur toutes les routes** (et pas seulement les routes de vote), code de statut et durée. Les journaux d'accès d'uvicorn sont désactivés.
- L'horodatage utilise `record.created`, pas l'heure de formatage.
- **Lint** : Ruff avec `UP` interdit `typing.Union`, `typing.Callable` et `typing.Coroutine`. Utiliser `X | Y` et `collections.abc`. `model_config = SettingsConfigDict(...)`.
- Les journaux d'accès n'incluent pas les query strings des routes `/api/v/*` (vote). Le préfixe est réservé dès maintenant.

## `app/db/client.py` (PyMongo async, **jamais Motor**)
- `AsyncMongoClient(MONGODB_URI, uuidRepresentation="standard", tz_aware=True, w="majority", readConcernLevel="majority", retryWrites=True)`.
- Créé dans le `lifespan` de FastAPI, stocké dans `app.state` et fermé à l'arrêt. **Un seul client, une seule boucle d'événements** : il n'est jamais partagé entre threads.
- Différences avec Motor à respecter :
  - `find()` est synchrone et renvoie un `AsyncCursor`, à parcourir avec `async for` ;
  - `to_list(None)` ;
  - pas de paramètre `io_loop` ni `connect` ;
  - `(await col.insert_one(d)).inserted_id`.
- `get_db()` n'est utilisable que depuis `repositories/` (contrôlé par le test d'architecture).
- **`run_in_transaction(client, fn)`** : `session.with_transaction(callback, read_concern=ReadConcern("majority"), write_concern=WriteConcern("majority"), read_preference=ReadPreference.PRIMARY)`. **Aucune boucle de relance maison.**
  - `with_transaction` relance **le callback** sur `TransientTransactionError`, et **seulement la validation** sur `UnknownTransactionCommitResult`. Une boucle maison qui réexécuterait tout après un `UnknownTransactionCommitResult` peut créer un **bulletin en double** en mode anonyme.
  - Vérifier dans la documentation PyMongo la forme exacte de `start_session` et `with_transaction` en API asynchrone (avec ou sans `await`).
- **Règles du callback** :
  1. il ne fait que des opérations en base, **toutes avec `session=session`** ;
  2. **aucun effet de bord hors base** (e-mail, compteur en mémoire, journal de succès) : il peut être réexécuté. Ces actions viennent **après** le retour ;
  3. il n'avale jamais une `PyMongoError` (sinon perte des étiquettes de relance). Les erreurs métier (`AlreadyConsumed`, `VersionClosed`, `LimitReached`) sont levées et annulent la transaction ;
  4. les valeurs aléatoires (UUID, `rand_key`) sont générées **dans** le callback.
- **Tests au lot 0** (`mongod` de test lancé avec `--setParameter enableTestCommands=1`, **jamais en production**), avec `configureFailPoint` `failCommand` :
  - étiquette `TransientTransactionError` sur `insert` (une fois) → callback exécuté deux fois, un seul document ;
  - étiquette `UnknownTransactionCommitResult` sur `commitTransaction` (une fois) → callback exécuté **une seule fois**, validation relancée, un seul document ;
  - erreur métier levée dans le callback → rien n'est écrit, l'exception remonte.

## `app/db/schemas/` (un fichier par collection, `SCHEMA: dict`)
- **Toutes** les collections de la section 6 de `PROMPT_MVP.md`, **sans exception**, y compris `auth_tokens` et `participant_links` (domaine identité), avec `bsonType: "object"`, `required`, `properties` et **`additionalProperties: false`**.
- Champs `_id` :
  - **domaine vote** : chaîne avec le motif UUID v4 `^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$` ;
  - **autres domaines** : `objectId`.
- **Dates des domaines vote et identité** (`submitted_on`, `consumed_on`, `sent_on`) : `{"bsonType":"string","pattern":"^\\d{4}-\\d{2}-\\d{2}$"}`. Un validateur `$jsonSchema` ne peut pas vérifier l'absence d'heure dans un type `date`.
- Dates de plateforme (`created_at`, `expires_at`, `at`…) : `bsonType: "date"`.
- Énumérations : `status`, `role`, `participation_mode`, `vote_preset`, `color_key` (`++`, `+`, `~`, `-`, `--`), `comment_status`, `kind`, `purpose`, `type`.
- `anonymity_threshold` : `int`, `minimum: 3`.
- `__init__.py` expose `ALL_SCHEMAS: dict[str, dict[str, Any]]`, `VOTE_DOMAIN = {"ballots","votes","segment_answers","general_answers"}` et `IDENTITY_DOMAIN = {"participants","participant_links","credential_uses","email_logs"}`.
- **`additionalProperties: false` à chaque niveau d'imbrication**, pas seulement à la racine :
  - `entitlements` et `settings` : propriétés listées explicitement ;
  - `usage` (clés dynamiques) : `patternProperties: {"^\\d{4}-\\d{2}$": {...}}`, chaque sous-objet de mois listant ses compteurs ;
  - **chaque tableau déclare son schéma `items`** : `groups[]` (chaînes de 1 à 100 caractères), `option_ids[]`, `allowed_email_domains[]`, `options[]` et `number_buckets[]` (objets fermés).
- Un test vérifie que **chaque** schéma déclare `additionalProperties: false`, et que `ALL_SCHEMAS` contient exactement les collections de la section 6.
- Pour chaque collection, un champ supplémentaire **à la racine, dans un sous-objet et dans un élément de tableau** est rejeté par MongoDB.

### Schémas particuliers
**`auth_tokens`** (plateforme, jetons des animateurs) :
| Champ | Type | Règle |
|---|---|---|
| `_id` | objectId | |
| `admin_id` | objectId | requis |
| `purpose` | énumération | `verify_email`, `reset_password` (`magic_link_admin` réservé, inutilisé au MVP) |
| `token_hash` | string | `^[0-9a-f]{64}$` |
| `expires_at` | date | 24 h (`verify_email`) ou 30 min (`reset_password`) |
| `used_at` | date | optionnel, posé une seule fois |

- Consommation atomique : `find_one_and_update({token_hash, purpose, used_at: null, expires_at: {$gt: now}}, {$set: {used_at: now}})`. Toujours vérifier `expires_at > now`, car le TTL ne passe qu'environ toutes les 60 s.
- Une nouvelle demande supprime les jetons non utilisés de même `admin_id` et `purpose`. Une réinitialisation réussie supprime tous les jetons `reset_password` de l'admin et révoque ses sessions.
- Index : `token_hash` unique, TTL sur `expires_at`, `(admin_id, purpose)`.

**`participant_links`** (identité, liens magiques du mode ouvert, implémentés au lot 3) :
| Champ | Type | Règle |
|---|---|---|
| `_id` | objectId | |
| `organization_id` | objectId | requis |
| `version_id` | objectId | requis |
| `email_normalized` | string | requis, produit par `normalize_email` |
| `token_hash` | string | `^[0-9a-f]{64}$` |
| `expires_at` | **date** | 15 min. Exception à la règle des dates en chaîne (TTL), consignée dans D016 |

- **Ni `used_at` ni `created_at`.** Usage unique par **suppression** : `find_one_and_delete({token_hash, expires_at: {$gt: now}})`. Aucune trace horodatée de l'instant de connexion ne subsiste.
- Au plus 3 liens actifs par `(version_id, email_normalized)` ; au-delà, le plus ancien est supprimé.
- Index : `token_hash` unique, TTL sur `expires_at`, `organization_id`, `(version_id, email_normalized)` non unique.
- Repository : `create`, `consume(token_hash) -> EmailIdentity | None`, `purge_version`. Aucune lecture par e-mail exposée hors du service d'authentification des participants.

## `app/db/indexes.py`
Liste déclarative, avec un **nom explicite et stable** pour chaque index :
- **Uniques** : `organizations(slug)`, `admins(email)`, `admin_sessions(token_hash)`, `auth_tokens(token_hash)`, `participant_links(token_hash)`, `evaluations(organization_id, slug)`, `credential_uses(version_id, credential_fingerprint)`, `votes(ballot_id, item_id)`, `segment_answers(ballot_id, question_id)`, `general_answers(ballot_id, question_id)`.
- **Uniques partiels** : `participants(version_id, email)` et `participants(token_hash)`, avec `partialFilterExpression` `{"<champ>": {"$exists": true, "$type": "string"}}`.
- **TTL** : `auth_tokens(expires_at)` et `participant_links(expires_at)`, `expireAfterSeconds: 0`.
- **Simples** : `ballots(version_id, rand_key)`, et `organization_id` sur chaque collection métier.

## `app/db/migrations.py` (idempotent, dans le `lifespan`, avant le seed)
1. Vérifier le réplica set avec la commande **`hello`** (présence de `setName`). Sinon, échec explicite.
2. Pour chaque collection : `createCollection` avec le validateur si elle est absente, sinon `collMod` (`validator`, `validationLevel: "strict"`, `validationAction: "error"`).
3. Créer les index. Si un index du même nom a une autre définition : échec explicite, **jamais** de suppression silencieuse.
4. Profiler désactivé (`profile: 0`), `slowms` selon `MONGO_SLOWMS` (élevé en production).
5. **Contrôle de rotation de clé** : si une version `open` a un `credential_key_id` différent de celui de la configuration, échec avec le message « rotation de CREDENTIAL_HMAC_KEY interdite tant qu'une version est ouverte ».
6. **En production** : échec si `admin@demo.example.com` ou `other@demo.example.com` existe.

Un journal résume les créations et modifications, sans aucune donnée.

## `app/main.py`
- `create_app()`, avec un `lifespan` qui crée le client, applique les migrations, exécute le seed si c'est autorisé, et démarre un `AsyncIOScheduler` vide (APScheduler 3.x, même boucle).
- Toutes les routes métier sous `/api`. Pas de CORS (même domaine via le proxy). Middleware d'en-têtes de sécurité.
- `GET /health` : `{"status":"ok"}` publiquement ; le détail (réplica set, migrations) seulement si `ENVIRONMENT=development`.

## `app/db/seed.py`
- Exécuté si `SEED_DEMO=true` **et** `ENVIRONMENT=development`, de façon idempotente (`upsert`).
- Organisation « Démo » (`plan_code: "trial"`) avec `admin@demo.example.com` / `admin`, et organisation « Autre » avec `other@demo.example.com` / `admin`, pour les tests d'isolation.
- Mots de passe hachés en argon2id, en **contournant la politique de mot de passe**. C'est le **seul** endroit du code où ce contournement est autorisé.

## `backend/scripts/export_openapi.py`
Importe `create_app()` sans connexion et écrit l'OpenAPI sur la sortie standard, au format JSON déterministe (`indent=2`, `sort_keys=True`, `ensure_ascii=False`, retour à la ligne final).

## Tests du bloc
- `Settings` : secret manquant, secrets identiques, secret trop court, règles de production (y compris le nombre de workers) → échec.
- Migrations : un second passage ne fait aucune modification ; un index en conflit provoque un échec.
- **Pour chaque collection** : un document valide est accepté, et le même document avec un champ supplémentaire est rejeté **par MongoDB**.
- Domaine vote :
  - rejet des champs `credential_fingerprint`, `participant_id`, `email`, `token`, `created_at` et `updated_at` ;
  - rejet d'une date de type `date` ou d'une chaîne avec heure ;
  - rejet d'un `_id` qui n'est pas un UUID v4.
- `anonymity_threshold = 2` → rejeté.
- Rotation de clé avec une version ouverte → démarrage en échec. Absence de réplica set → échec. Production avec comptes de démonstration → échec.
- `create_app()` et `app.openapi()` fonctionnent sans MongoDB.
