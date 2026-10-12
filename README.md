# Abaque

SaaS d'évaluation collective fondé sur l'abaque de François Régnier : vote en 5 couleurs, commentaires argumentés, segmentation des participants, matrices de consensus et de dissensus, exports CSV et PDF.

- Multi-organisations, droits par offre, version démo.
- Anonymat des votes garanti par conception : aucune donnée applicative ne relie un bulletin à une identité ; seuil k appliqué côté serveur.
- Hébergement dans l'UE, de préférence en France.

## Prérequis
- Docker et Docker Compose v2.
- En option, hors conteneur : Node 24 (`.nvmrc`) et Python 3.13 avec uv.

## Démarrage
```bash
cp .env.example .env
# générer trois secrets DIFFÉRENTS :
openssl rand -hex 32   # JWT_SECRET
openssl rand -hex 32   # CREDENTIAL_HMAC_KEY
openssl rand -hex 16   # IP_HASH_SALT
docker compose up
```
- Front : http://localhost:5173
- API : http://localhost:8000 (documentation sur `/docs`)
- Santé : http://localhost:8000/health
- Compte de développement : `admin@abaque.local` / `admin` (seed, développement uniquement)

## Commandes
```bash
docker compose exec api uv run pytest            # tests backend
docker compose exec api uv run ruff check .      # lint backend
docker compose exec api uv run mypy .            # typage backend
docker compose exec web npm test                 # tests frontend
docker compose exec web npm run lint             # lint frontend
docker compose exec web npm run typecheck        # typage frontend
docker compose build api                         # après un changement de dépendances Python
docker compose build web                         # après un changement de dépendances npm
docker compose down -v                           # remise à zéro complète
```

## Documentation
- [`docs/PROMPT_MVP.md`](docs/PROMPT_MVP.md) : spécification, seule référence.
- [`docs/architecture/`](docs/architecture/README.md) : spécifications techniques détaillées.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) : décisions prises hors spécification.
- [`docs/adr/0001-stack.md`](docs/adr/0001-stack.md) : stack et garde-fous.
- [`docs/CHANGELOG.md`](docs/CHANGELOG.md) : état d'avancement.
- [`docs/PROMPT_RELANCE.md`](docs/PROMPT_RELANCE.md) : prompt pour relancer le développement avec un agent.

## Licence
Tous droits réservés. Voir [LICENSE](LICENSE).
