# ADR 0001 — Stack technique

- **Statut** : accepté
- **Date** : 2026-10-12

## Contexte
La stack est **imposée par l'environnement de réalisation** : ce n'est pas un choix d'architecture. Le modèle métier est relationnel (versions → groupes → items ; bulletins → votes ; segmentation), et les garanties critiques reposent sur l'unicité, l'atomicité et le k-anonymat.

## Décision
| Couche | Choix |
|---|---|
| Front | React 19, TypeScript strict, Vite 8, React Router 7 (mode bibliothèque), `openapi-typescript` + `openapi-fetch`, Node 24 LTS |
| Back | Python 3.13, FastAPI, Pydantic v2, pydantic-settings, PyJWT, argon2-cffi, uv (`uv.lock` commité) |
| Base | MongoDB 7.0 via `pymongo.AsyncMongoClient` (**Motor interdit**), hébergée dans l'UE, de préférence en France |
| Tâches planifiées | APScheduler 3.x, `AsyncIOScheduler`, même boucle que l'API |
| PDF / CSV | Côté serveur (WeasyPrint dans `run_in_executor`), uniquement à travers `anonymity` |
| E-mail | Interface `Mailer` (console en développement, fournisseur européen ensuite) |
| Local et CI | Docker Compose, MongoDB en réplica set **mono-nœud** |
| Production | 1 worker uvicorn derrière nginx (même domaine), réplica set à 3 nœuds ou Atlas UE |

## Garde-fous obligatoires
1. **Réplica set partout** (développement, CI, production), indispensable aux transactions. Vérifié au démarrage avec `hello`.
2. **Validateurs `$jsonSchema`** sur **toutes** les collections : `validationLevel: strict`, `validationAction: error`, **`additionalProperties: false`**. Appliqués par des migrations idempotentes (`createCollection` / `collMod`).
3. **Domaine vote** : `_id` en chaîne UUID v4 validée par motif (jamais d'ObjectId, qui contient l'heure de création) ; dates en chaîne `YYYY-MM-DD` validée par motif (un type `date` ne permet pas de vérifier l'absence d'heure) ; aucun horodatage automatique.
4. **Index** : voir `docs/architecture/lot0-03-core-db.md`. Noms stables ; aucune suppression silencieuse.
5. **Transactions** : `session.with_transaction` avec `majority`, pour le vote, la régénération de jeton, les compteurs d'usage et le cycle de vie des versions. Pas de boucle de relance maison (risque de double écriture après `UnknownTransactionCommitResult`).
6. **Séparation des domaines** : identité (`participants`, `participant_links`, `credential_uses`, `email_logs`) et vote (`ballots`, `votes`, `segment_answers`, `general_answers`), avec `version_id` pour seul point de contact.
7. **Isolation multi-organisations** : `organization_id` injecté par les repositories depuis le jeton, jamais depuis le client. Aucun accès à une collection hors de `repositories/` et `db/`. Le super-administrateur passe par des repositories `platform_*` sans accès aux domaines vote et identité.

## Couche repository = voie de migration vers PostgreSQL
Le domaine dépend de protocoles. `vote_engine`, `anonymity` et `entitlements` sont du Python pur, sans aucun import de base de données. Migrer reviendrait à :
1. réécrire les implémentations des repositories ;
2. remplacer les validateurs par des contraintes SQL ;
3. rejouer la même suite de tests.

## Conséquences et risques résiduels
- Garanties moins lisibles qu'en SQL, compensées par les validateurs et les tests (propriétés, concurrence, architecture).
- Agrégations dans `vote_engine` à partir des bulletins filtrés, pas dans des pipelines `$group`. Le moteur reste l'unique point de calcul et de filtrage k.
- **Oplog et sauvegardes** : ils conservent groupées les opérations d'une même transaction, donc le marqueur `credential_uses` et le bulletin. Mesures : oplog de taille minimale, accès réservé à l'exploitation, sauvegardes chiffrées à rétention courte, mention dans le DPA et le registre.
- **Journaux de la base** : profiler désactivé, `slowms` élevé, aucune journalisation des requêtes complètes sur les routes de vote. Les textes d'exception (qui peuvent contenir des clés en double) sont masqués par le formateur de journaux.
- **Homogénéité** : un segment d'au moins k bulletins tous de la même couleur révèle le vote de ses membres. Documenté, non corrigé au MVP.
- **Un seul worker** (D013) tant que la limite de débit est en mémoire et que le scheduler tourne dans l'API.

## Critères de réévaluation
- Un audit externe qui exige des garanties exprimées en SQL.
- Plus de 10 000 bulletins par version.
- Un changement d'environnement de réalisation.
