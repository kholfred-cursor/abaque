# Changelog

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/). Une section par lot : livré, ouvert, reporté.

## [Non publié]

### Cadrage (2026-10-12)
- Spécification `docs/PROMPT_MVP.md` figée (SaaS multi-organisations, anonymat, 6 lots).
- Dossier `docs/architecture/` : spécifications détaillées du lot 0 (blocs 1 à 7) et des garanties (transaction de vote, anonymat, exports, tests du lot 2, production).
- `docs/DECISIONS.md` : D001 à D031.
- `docs/adr/0001-stack.md`.

### Lot 0 — Socle (en cours)
- Blocs 1 et 2 produits puis corrigés (types OpenAPI commités, virtualenv hors du volume, nginx avec en-têtes par `location` et proxy `/api`, 1 worker, secrets de CI générés, SHA vérifiés, Dependabot uv avec groupes).
- Bloc 3 : partie a corrigée et validée (sous réserve des ajustements de lint : imports inutilisés, `per-file-ignores`, `noqa` inutile, code de sortie du script de mots de passe) ; partie b à produire. Historique : (voir `docs/architecture/lot0-03-core-db.md`, `lot0-05-auth-api.md` et `vote-transaction.md`). Précisions ajoutées : transactions via `with_transaction` (D024), normalisation des e-mails (D023), schémas `auth_tokens` et `participant_links`, `additionalProperties: false` à chaque niveau.

- **Instantané Git (2026-10-12, branche `lot-0-socle`)** — travail en cours, blocs 1, 2, 3a et 3b partie 1/2 : Docker, Compose, nginx, CI, Dependabot, `pyproject.toml`, `core/` (config, identity, security, logging, middleware), `db/client.py`, `db/schemas/` (21 schémas `$jsonSchema`), liste de mots de passe courants, `scripts/export_openapi.py`, `backend/uv.lock` (81 paquets). D026 ajoutée.
- Manquent encore (bloc 3b partie 2/2 et suivants) : index, migrations, `app/main.py`, seed, repositories, API, tests, `frontend/package.json`. **La CI échoue tant qu'ils n'existent pas** : c'est attendu sur cette branche.

- **Bloc 3b partie 2/2 (2026-10-12)** : `db/indexes.py` (34 index nommés), `db/migrations.py` (idempotent : validateur modifié seulement s'il diffère, conflit d'index → échec, rotation de clé, comptes de démo interdits en production), `db/seed.py`, `app/main.py` (`create_app`, `lifespan`, `/health`). Corrections de relecture : requête de rotation `$nin [null, clé]`, index `participant_links(version_id, email_normalized)`, `export_openapi.py` exécutable depuis `backend/`, nginx sans doublons d'en-têtes sur `/api` et `/health`, lint des schémas. Tests MongoDB du bloc à écrire.
- **Tests du bloc 3 (2026-10-12)** : 106 tests, tous verts sur MongoDB 7.0 en réplica set (`enableTestCommands`), couverture 96 %. 66 écrits par l'agent (Settings, migrations, 21 validateurs, domaine vote, seed) ; fabrique de documents corrigée (motifs UUID, jour, mois, SHA-256) et tests négatifs renforcés (le document de base est d'abord prouvé valide). Ajoutés à la relecture : identité, sécurité, journaux, middleware, `create_app` et `/health`. CI : `MONGODB_TEST_URI`.
- **Bloc 3c — squelette front (2026-10-12)** : `package.json` et `package-lock.json`, Vite 8, TypeScript strict, ESLint (TypeScript, react-hooks, jsx-a11y, interdiction de `dangerouslySetInnerHTML` et du stockage local), Prettier, Vitest, `gen:api` et `schema.d.ts` commité, client `openapi-fetch`, routes `/`, `/v/:slug` et 404 avec 3 tests. Les vrais écrans restent au bloc 7. D027.
- **Bloc 4a (2026-10-12)** : `entitlements` (plans, résolution, contrôles), `domain` (modèles, erreurs, `TenantContext`, ports de tous les repositories y compris lots 1 à 3), `repositories/mongo` (`TenantScopedRepository`, organisations, admins, authentification). Corrections de relecture : droits stockés en surcharges et recalculés à la lecture, `OrganizationProvisioningRepository` pour l'inscription au lieu d'un faux contexte, `AlreadyConsumed`, interfaces figées des lots 1 à 3, tests ajoutés (atomicité par `failCommand`, quota d'animateurs, changement d'offre, surcharges invalides, isolation des listes et de l'usage). 121 tests, couverture 93 %. D028.
- **Bloc 4b (2026-10-12)** : `AdminSessionRepository` (rotation atomique en transaction, détection de réutilisation), `AuthTokenRepository` (un jeton actif par usage, consommation atomique), tests de concurrence, tests d'architecture par AST. Corrections de relecture : fenêtre de tolérance de 10 s (`ConcurrentRotation`) — sans elle, deux onglets qui se rafraîchissent ensemble déconnectaient l'utilisateur ; tests d'architecture rendus non vacants (contrôle du scanner, accès `ports.BallotReaderPort`). 131 tests, couverture 93 %. D029.
- **Bloc 5a (2026-10-12)**, réalisé hors de l'agent : format d'erreur unique, dépendances (`current_admin`, `require_verified`, `require_role`, `current_org`, CSRF à double soumission), 3 cookies conformes à la spécification, limite de débit en mémoire, `Mailer` (console en développement, refusé en production), routes `login`, `refresh` (409 en cas de course entre onglets, 401 et révocation globale en cas de rejeu), `logout`, `me`, `organization`. `MongoStore` (D030), D020 tranchée (403). 24 tests HTTP, dont des tests de non-régression vérifiés par mutation (CSRF désactivé, cookie affaibli). 155 tests, couverture 93 %. Types OpenAPI du front régénérés.
- **Bloc 5b (2026-10-12)**, réalisé hors de l'agent : inscription (organisation en essai et propriétaire non vérifié, réponse neutre), vérification de l'e-mail et renvoi, mot de passe oublié et réinitialisation (révocation de toutes les sessions), changement de mot de passe (révocation des autres sessions), liste et révocation des sessions avec description courte de l'appareil. D031. 18 tests HTTP, dont deux vérifiés par mutation. 173 tests, couverture 93 %.

#### Reporté au lot 1
- Activation du job CI `e2e` (premier parcours Playwright : vote anonyme sur viewport mobile).
- Fichiers `docs/samples/items.csv` et `participants.csv`.
