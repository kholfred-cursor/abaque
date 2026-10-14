# Dossier d'architecture — Abaque

Ce dossier détaille **comment** construire ce que `docs/PROMPT_MVP.md` décrit. En cas d'écart, `PROMPT_MVP.md` l'emporte ; toute modification se fait dans les deux fichiers, dans le même commit.

État d'avancement : voir [`../AVANCEMENT.md`](../AVANCEMENT.md).

## Lot 0 — Socle (un fichier par bloc de livraison)

| Bloc | Fichier | Contenu |
|---|---|---|
| 1 | [`lot0-01-racine-docs.md`](lot0-01-racine-docs.md) | Fichiers racine, documentation, licence |
| 2 | [`lot0-02-docker-ci.md`](lot0-02-docker-ci.md) | Docker Compose, Dockerfiles, nginx, CI, Dependabot |
| 3 | [`lot0-03-core-db.md`](lot0-03-core-db.md) | Configuration, journaux, client MongoDB, schémas, index, migrations, seed |
| 4 | [`lot0-04-repositories-entitlements.md`](lot0-04-repositories-entitlements.md) | Repositories, isolation multi-organisations, droits par offre |
| 5 | [`lot0-05-auth-api.md`](lot0-05-auth-api.md) | Authentification animateur, cookies, CSRF, routes |
| 6 | [`lot0-06-tests-backend.md`](lot0-06-tests-backend.md) | Infrastructure de tests, tests d'architecture et d'isolation |
| 7 | [`lot0-07-frontend.md`](lot0-07-frontend.md) | Socle React, client API, authentification, tokens de design |

## Lot 1

| Fichier | Contenu |
|---|---|
| [`lot1-plan.md`](lot1-plan.md) | Découpage en blocs 1a à 1e et choix D035 à D043 |

## Garanties (lots 2 à 4)

| Fichier | Contenu |
|---|---|
| [`vote-transaction.md`](vote-transaction.md) | Écriture d'un vote, `credential_uses`, fingerprint, cas d'erreur |
| [`anonymity.md`](anonymity.md) | Module `anonymity`, seuil k, complément, homogénéité |
| [`exports.md`](exports.md) | Les 3 exports CSV et le rapport PDF |
| [`tests-garanties-lot2.md`](tests-garanties-lot2.md) | Tests de propriétés, de concurrence, de clôture, de métadonnées |

## Exploitation

| Fichier | Contenu |
|---|---|
| [`production.md`](production.md) | Worker unique, proxy, en-têtes, TLS, sauvegardes, conditions de passage à l'échelle |

## Ordre de lecture pour un agent qui reprend le projet
1. `docs/PROMPT_MVP.md` (spécification complète) ;
2. `docs/DECISIONS.md` (décisions prises hors spécification) ;
3. `docs/adr/0001-stack.md` ;
4. ce dossier, dans l'ordre des lots ;
5. `docs/CHANGELOG.md` (état d'avancement réel).
