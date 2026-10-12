# Lot 0 — Bloc 4 : repositories et `entitlements`

## Principes
- Le domaine dépend de **protocoles** (`typing.Protocol`) définis dans `app/domain/ports.py`. Les implémentations PyMongo sont dans `app/repositories/mongo/`.
- **Seuls** `app/repositories/` et `app/db/` importent `pymongo` ou `bson`.
- Les repositories prennent et renvoient des **modèles Pydantic du domaine** (`app/domain/models.py`), jamais des `dict` bruts.
- Chaque méthode accepte un paramètre optionnel `session`, pour pouvoir être composée dans `run_in_transaction`.

## Isolation multi-organisations
- `TenantContext(organization_id, admin_id, role)` est construit **uniquement** par la dépendance FastAPI `current_org`, à partir du JWT.
- Les repositories métier sont instanciés par requête avec ce contexte. Chaque lecture ajoute `organization_id` au filtre. Chaque écriture **force** `organization_id = ctx.organization_id` et écrase toute valeur fournie.
- Ressource absente ou appartenant à une autre organisation → `NotFound` → **404**, jamais 403.
- Classe de base `TenantScopedRepository` : `_scope(filter)` ajoute l'`organization_id`, et lève une exception si le filtre contient un `organization_id` différent.
- Repositories **hors organisation**, explicitement nommés :
  - `AdminAuthRepository` (connexion par e-mail) ;
  - `AdminSessionRepository` et `AuthTokenRepository` (recherche par `token_hash`) ;
  - `platform/PlatformOrganizationRepository` (super-administrateur : liste, changement d'offre, suspension). **Aucun accès** aux domaines vote et identité.

## Implémentés au lot 0
- `OrganizationRepository` :
  - `create_with_owner` (transaction) ;
  - `get_current` ;
  - `get_entitlements` ;
  - `increment_usage(month, key, n, session)` (`$inc` sur `usage.YYYY-MM.key`).
- `AdminRepository` : `get`, `list`, `create_animator` (soumis à `max_animators`).
- `AdminAuthRepository` : `find_by_email`, `create_owner`, `mark_email_verified`, `set_password_hash`.
- `AdminSessionRepository` :
  - `create` ;
  - `rotate`, atomique avec `find_one_and_update` sur `token_hash` et `revoked_at: null` ;
  - `revoke` et `revoke_all_for_admin` ;
  - `find_by_hash` ;
  - `mark_consumed` (détection de réutilisation).
- `AuthTokenRepository` : `create(purpose)` et `consume(token_hash, purpose)`, atomique (`used_at` posé une seule fois).

## Interfaces figées dès le lot 0 (implémentation plus tard)
- **Lot 1** : `EvaluationRepository`, `VersionRepository`, `ItemRepository`, `SegmentQuestionRepository`, `GeneralQuestionRepository`.
- **Lot 2** :
  - **`BallotWriter`** : une seule méthode d'écriture, `write_ballot(...)`, appelée dans la transaction de vote. Aucune mise à jour ni suppression unitaire ; seulement `purge_version`.
  - **`BallotReader`** : bulletins **triés par `rand_key`** uniquement. Aucune méthode qui trie par `_id` ou par ordre naturel.
  - **`CredentialUseRepository`** : seulement `consume(version_id, fingerprint, key_id, day, session)` (lève `AlreadyConsumed`) et `purge_version`. **Aucune lecture par fingerprint.**
- **Lot 3** : `ParticipantRepository`, `ParticipantLinkRepository`.
- Seuls `app/anonymity`, `app/services/restitution` et `app/services/export` peuvent importer `BallotReader`.

## Module `entitlements` (Python pur, `app/entitlements/`)
- `models.py` : `Entitlements`, modèle Pydantic figé avec 9 clés :
  - `max_active_evaluations`, `max_ballots_per_version`, `max_animators` (entier, `None` = illimité) ;
  - `modes_allowed` (liste) ;
  - `pdf_export`, `csv_export`, `email_invitations`, `custom_branding` (booléens) ;
  - `retention_months`.
- `plans.py` : `PLAN_DEFAULTS` pour `demo`, `trial` et `standard`, avec des valeurs **provisoires** marquées « TODO tarifs » :
  - **trial** : 1 évaluation, 30 bulletins par version, 1 animateur, `modes_allowed=["anonymous"]`, PDF et CSV oui, e-mails non, personnalisation non, rétention 1 mois ;
  - **demo** : comme `trial`, avec 300 bulletins par version ;
  - **standard** : valeurs larges, rétention 12 mois.
- `checker.py` :
  - `resolve(plan_code, overrides)` ;
  - `check_limit(ent, key, current)` → `LimitReached` ;
  - `check_feature(ent, key)` → `FeatureNotAllowed` ;
  - `check_mode(ent, mode)`.
- Aucun import de `pymongo` ni de `fastapi`. La traduction HTTP se fait dans `api/` (code 402 ou 403 au choix, consigné dans `DECISIONS.md`), avec le message « Limite de votre offre atteinte ».
- `max_ballots_per_version` : le module **calcule** la limite, mais la vérification se fait **dans** l'`update_one` atomique de la transaction de vote (voir `vote-transaction.md`), jamais par une lecture suivie d'une écriture.

## Tests du bloc
- **Isolation** :
  - un repository avec le contexte A ne lit, ne modifie ni ne supprime rien de B ;
  - un `organization_id` passé dans les données est écrasé ;
  - un filtre contradictoire lève une exception.
- **Sessions** : deux `rotate` concurrents → un seul succès ; réutilisation d'un jeton consommé → `revoke_all_for_admin`.
- **`AuthTokenRepository.consume`** : usage unique, y compris en concurrence ; jeton expiré refusé.
- **`create_with_owner`** : atomique.
- **`entitlements`** : résolution plan + valeurs propres, limite atteinte ou non, `None` illimité, fonctionnalité refusée, mode refusé.
- **Architecture** :
  - `entitlements` n'importe ni `pymongo` ni `fastapi` ;
  - `platform/` n'importe pas les repositories des domaines vote et identité ;
  - `BallotReader` n'est importé que par les modules autorisés.
