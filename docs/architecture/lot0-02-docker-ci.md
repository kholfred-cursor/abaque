# Lot 0 — Bloc 2 : Docker, CI, Dependabot

## `docker-compose.yml` (développement)
| Service | Exigences |
|---|---|
| `mongo` | `mongo:7.0`, commande `["--replSet","rs0","--bind_ip_all"]`, volume nommé `mongo-data`, port `127.0.0.1:27017:27017`. Healthcheck `mongosh --quiet --eval "db.adminCommand('ping').ok"`. |
| `mongo-init` | `mongo:7.0`, `depends_on: mongo (service_healthy)`, `restart: "no"`, script monté en lecture seule dans **`/scripts/mongo-init.sh`** (jamais dans `/docker-entrypoint-initdb.d/`). |
| `api` | Build `backend/` cible `dev`, `env_file: .env`, `depends_on: mongo-init (service_completed_successfully)`, volume `./backend:/app`, port `127.0.0.1:8000:8000`, commande `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`. Healthcheck sur `/health`. |
| `web` | Build `frontend/` cible `dev`, volumes `./frontend:/app` et volume anonyme `/app/node_modules`, port `127.0.0.1:5173:5173`, commande `npm run dev -- --host`. Proxy Vite `/api` et `/health` vers `http://api:8000`. |

Aucun secret dans le compose.

Pour les tests locaux, un fichier `docker-compose.test.yml` (ou un profil `test`) ajoute `--setParameter enableTestCommands=1` au service `mongo`. Le compose de développement « normal » ne l'active pas.

### `docker/mongo-init.sh` (idempotent)
1. `mongosh --quiet --eval` avec `try { rs.status() } catch (e) { if (e.codeName === "NotYetInitialized") rs.initiate({_id:"rs0",members:[{_id:0,host:"mongo:27017"}]}); else throw e }`.
2. Attendre `db.hello().isWritablePrimary === true` pendant 30 s au plus.
3. Code 0 si le primaire est prêt ; sinon message explicite et code 1. Toute erreur autre que `NotYetInitialized` fait échouer le script.

Vérification : `docker compose up` deux fois, puis `docker compose restart mongo-init` → code 0 à chaque fois, avec « déjà initialisé ».

## `backend/Dockerfile` (multi-étapes)
- Étape `base` : `python:3.13-slim`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, **`UV_PROJECT_ENVIRONMENT=/opt/venv`**, **`UV_FROZEN=1`**, uv copié depuis `ghcr.io/astral-sh/uv:<version épinglée>` (même version qu'en CI, voir D012).
- Étapes `dev` et `prod` : `uv sync --frozen` (sans dépendances de développement en `prod`), puis création de l'utilisateur `app` (uid 1001), **`chown -R app:app /opt/venv` après `uv sync` et avant `USER app`**.
- `prod` : `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips=<réseau interne>` (voir `production.md`).
- WeasyPrint et ses dépendances système **ne sont pas** installés avant le lot 4.

## `frontend/Dockerfile` (multi-étapes)
- `node:24-alpine`, `npm ci`.
- Cible `dev` : Vite.
- Cible `build` : `npm run build`.
- Cible `prod` : image nginx épinglée, fichiers de `dist/`, configuration ci-dessous.

## nginx de production (`frontend/docker/`)
- **`security-headers.conf` inclus dans CHAQUE bloc `location`**. Un `add_header` dans un `location` annule l'héritage de ceux du bloc `server`. Contenu :
  - `Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'` ;
  - `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`.
- **`hsts.conf`** (`Strict-Transport-Security`) inclus **uniquement** dans la configuration TLS de production, jamais en http local.
- `location /` : repli SPA vers `index.html`. Assets : cache long et immuable. `index.html` : `no-cache`.
- **`location /api/ { proxy_pass http://api:8000; }`, sans barre finale** : le préfixe `/api` est conservé, car les routes FastAPI sont sous `/api`. En-têtes `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`. `Cache-Control: no-store`. `client_max_body_size 2m`, `proxy_read_timeout 30s` (60 s sur `/api/exports/` au lot 4).
- `location = /health` : proxy vers l'API.
- Compatibilité de la CSP : aucune bibliothèque CSS-in-JS qui injecte des `<style>`. Les CSS Modules et `element.style` sont compatibles.

### `scripts/check-headers.sh` (lancé en CI contre l'image de production)
Vérifie sur `/`, `/index.html`, un fichier de `/assets/` et `/api/health` : présence de la CSP, de `X-Frame-Options`, de `X-Content-Type-Options` et de `Referrer-Policy`. Vérifie aussi que `/api/health` renvoie 200 et que `/api/xyz` renvoie l'erreur 404 **JSON** de l'API, et non la page SPA.

## CI — `.github/workflows/ci.yml`
- Déclencheurs : `push` sur `main`, `pull_request`. `permissions: contents: read`.
- Job `changes` : `dorny/paths-filter` → `backend`, `frontend`.
- **Toutes les actions tierces sont épinglées par SHA vérifié** contre leur tag (`gh api repos/<owner>/<repo>/git/ref/tags/<tag>`), avec le tag en commentaire.
- **Secrets de test** : une seule étape réutilisable (action composite `.github/actions/test-secrets`), qui génère trois valeurs **différentes** avec `openssl rand -hex 32`, applique `::add-mask::` à chacune, et les écrit dans `$GITHUB_ENV`. Utilisée par `backend` et `contract`. Aucun secret en clair dans le workflow.
- Job `backend` :
  - MongoDB lancé par **`docker run`** (`mongo:7.0 --replSet rs0 --setParameter enableTestCommands=1`). Ce paramètre sert aux tests `failCommand` et n'est **jamais** activé en production. Les `services:` de GitHub Actions ne permettent pas de passer d'arguments.
  - Attente du ping, puis `rs.initiate` (hôte `localhost:27017`), puis attente du primaire. **Après chaque boucle d'attente : `docker logs mongo --tail 50` et `exit 1` en cas d'échec.**
  - `uv sync --frozen`, `ruff check`, `ruff format --check`, `mypy --strict`, `pytest` avec couverture (`--cov-fail-under=85`).
  - URI : `mongodb://localhost:27017/?replicaSet=rs0&directConnection=true`.
- Job `frontend` : Node 24 (`cache: npm`), `npm ci`, `lint`, `typecheck`, `test -- --run`, `build`, puis construction de l'image de production et `check-headers.sh`.
- Job `contract` :
  1. secrets de test ;
  2. `uv run python scripts/export_openapi.py > openapi.json` : le script importe `create_app()` **sans connexion à la base** et écrit `json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False)` suivi d'un retour à la ligne final ;
  3. `npm run gen:api` ;
  4. `git diff --exit-code frontend/src/shared/api/schema.d.ts`, avec un message explicite en cas d'écart.
- Job `e2e` : présent mais `if: false`, avec le commentaire `# Activé au lot 1 : premier parcours Playwright (vote anonyme sur viewport mobile)`.
- uv : `astral-sh/setup-uv` avec `version:` identique au tag de l'image Docker.

## `.github/dependabot.yml`
- Écosystèmes : **`uv`** (`/backend`), `npm` (`/frontend`), `docker` (`/backend`, `/frontend`), **`docker-compose`** (`/`, image `mongo`), `github-actions` (`/`).
- Fréquence hebdomadaire. **Groupes** : mineures et correctifs regroupés par écosystème. **Majeures jamais groupées**, une PR chacune.
- Image `mongo` : `ignore` des montées majeures (`version-update:semver-major`). Changer de version majeure de MongoDB est une décision (D006), pas une PR automatique.
- 5 PR ouvertes au maximum par écosystème. Étiquettes `dependencies` et `backend`, `frontend`, `docker` ou `ci`.
