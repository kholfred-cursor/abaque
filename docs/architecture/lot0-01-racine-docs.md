# Lot 0 — Bloc 1 : racine et documentation

## Fichiers à la racine
| Fichier | Exigences |
|---|---|
| `README.md` | Présentation, prérequis (Docker Compose v2 ; Node 24 et Python 3.13 en option hors conteneur), démarrage (`cp .env.example .env` puis `docker compose up`), URL locales (front `:5173`, API `:8000`, `/docs`, `/health`), compte de développement `admin@abaque.local` / `admin`, commandes de test et de lint, reconstruction après un changement de dépendances (`docker compose build api` ou `web`), structure du monorepo, liens vers `docs/`. |
| `LICENSE` | `Copyright (c) 2026 [Titulaire des droits]. Tous droits réservés.` Le titulaire est complété par Fred. Jamais « Abaque » seul, qui n'est pas une personne juridique. |
| `.gitignore` | Voir ci-dessous. |
| `.nvmrc` | `24` |
| `.env.example` | Voir ci-dessous. |

### `.gitignore` : règles impératives
- Ignorer : caches Python, `.venv/`, `node_modules/`, `frontend/dist/`, `.env` et `.env.*` **sauf** `!.env.example`, `.vscode/*` **sauf** `!.vscode/extensions.json`, `.idea/`, fichiers système, `mongo-data/`, `exports/`, `*.log`, `reference/` (fichiers de référence externes, comme le prototype ToneVote, jamais publiés), `openapi.json` à la racine (fichier intermédiaire).
- **Ne jamais ignorer `frontend/src/shared/api/schema.d.ts`** : il est commité, et le job `contract` le compare à une régénération.

### `.env.example` : variables obligatoires
```
ENVIRONMENT=development
MONGODB_URI=mongodb://mongo:27017/abaque?replicaSet=rs0
DATABASE_NAME=abaque
# Les trois secrets sont obligatoires et doivent être DIFFÉRENTS (sinon refus de démarrer)
JWT_SECRET=            # 32 caractères minimum
CREDENTIAL_HMAC_KEY=   # 32 caractères minimum, jamais réutilisée ailleurs
IP_HASH_SALT=          # 16 caractères minimum
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=14
SEED_DEMO=true         # développement uniquement ; interdit en production
SIGNUP_ENABLED=true    # false par défaut en production jusqu'au lot 5
COOKIE_SECURE=false    # true obligatoire en production
APP_BASE_URL=http://localhost:5173
RATE_LIMIT_BACKEND=memory
WEB_CONCURRENCY=1      # 1 obligatoire tant que RATE_LIMIT_BACKEND=memory (voir production.md)
```
Les valeurs d'exemple des secrets restent vides ou portent la mention `change-me-…`. Le README indique comment les générer (`openssl rand -hex 32`).

## Documentation (`docs/`)
| Fichier | Rôle |
|---|---|
| `PROMPT_MVP.md` | Spécification, seule référence. Copiée telle quelle, jamais reformulée par l'agent. |
| `DECISIONS.md` | Une entrée par décision prise hors spécification, numérotée `Dnnn`, avec contexte, décision, conséquences et source quand un fait externe est cité. |
| `CHANGELOG.md` | Format « Keep a Changelog ». Une section par lot, avec ce qui est livré, ce qui reste ouvert, et les tâches reportées. |
| `adr/0001-stack.md` | Voir le fichier fourni. |
| `architecture/` | Ce dossier. |
| `design/scale.json` | Échelle de couleurs partagée par le front et le PDF. |
| `samples/` | `items.csv`, `participants.csv` (à partir du lot 1). |
