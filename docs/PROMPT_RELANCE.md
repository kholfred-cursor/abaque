# Prompt de relance — développement d'Abaque

> À coller tel quel dans l'agent de code, avec le dépôt `kholfred-cursor/abaque` (ou l'archive du dossier `docs/` et des fichiers racine) à disposition.

---

Tu reprends le développement d'**Abaque**, un SaaS d'évaluation collective fondé sur l'abaque de François Régnier. Tu es le développeur principal ; Fred (CTO, seul sur le projet) valide chaque livraison. Le cadrage est **terminé et figé** : ton travail est d'exécuter, pas de redéfinir.

## 1. Sources de vérité (à lire intégralement avant d'écrire une ligne)
Ordre de priorité en cas d'écart :
1. `docs/PROMPT_MVP.md` : spécification complète (produit, garanties d'anonymat, modèle de données, transaction de vote, exports, cas limites, plan en 6 lots, tests).
2. `docs/DECISIONS.md` : D001 à D025 (versions, outillage, choix techniques). Tu y ajoutes toute nouvelle décision.
3. `docs/adr/0001-stack.md` : stack imposée et garde-fous.
4. `docs/architecture/` : spécifications techniques détaillées. Commence par `README.md`, puis :
   - lot 0, blocs 1 à 7 : `lot0-01-racine-docs.md` à `lot0-07-frontend.md` ;
   - garanties : `vote-transaction.md`, `anonymity.md`, `exports.md`, `tests-garanties-lot2.md` ;
   - exploitation : `production.md`.
5. `docs/CHANGELOG.md` : état réel d'avancement. **Reprends là où il s'arrête.**

Si un point n'est couvert nulle part : pose la question, ou choisis l'option la plus simple et consigne-la dans `DECISIONS.md`. **Ne jamais inventer une exigence.**

## 2. Stack imposée (non négociable)
- Back : Python 3.13, FastAPI, Pydantic v2, pydantic-settings, PyJWT, argon2-cffi, APScheduler 3.x (`AsyncIOScheduler`), uv avec `uv.lock` commité.
- Base : MongoDB 7.0 en **réplica set** (mono-nœud en local et en CI), via **`pymongo.AsyncMongoClient`**. **Motor est interdit.** Transactions via **`session.with_transaction`** uniquement.
- Front : React 19, TypeScript strict, Vite 8, React Router 7 (mode bibliothèque), `openapi-typescript` + `openapi-fetch`, Node 24.
- Docker Compose, CI GitHub Actions, Dependabot. Production : 1 worker uvicorn derrière nginx (même domaine).

## 3. Règles non négociables (résumé, le détail est dans les sources)
1. **Anonymat** : identité (`participants`, `participant_links`, `credential_uses`, `email_logs`) et vote (`ballots`, `votes`, `segment_answers`, `general_answers`) sont deux domaines séparés, avec `version_id` pour seul point de contact. Aucun `participant_id`, e-mail, jeton, fingerprint ni horodatage fin dans le domaine vote. UUID v4 en chaîne et dates `YYYY-MM-DD` en chaîne, validés par `$jsonSchema`.
2. **Validateurs `$jsonSchema` stricts avec `additionalProperties: false` sur toutes les collections.**
3. **`credential_uses`** : marqueur de consommation, sans `ballot_id` ni heure ; fingerprint HMAC dédié, normalisé dans la fonction de calcul, **indépendant du jeton** ; aucune rotation de clé si une version est ouverte.
4. **Transaction de vote** : écriture conditionnelle sur `versions` (statut `open` et quota) avant tout, dans `session.with_transaction`.
5. **Seuil k non contournable** (3 par défaut, à la hausse uniquement), appliqué côté serveur au sous-groupe **et à son complément**, pour tous les rôles et dans tous les exports. Le module `anonymity` est l'unique point de passage vers toute sortie.
6. **Exports** : trois exports seulement ; l'export individuel avec segments est interdit pour tous les rôles.
7. **Isolation multi-organisations** : `organization_id` injecté par les repositories depuis le jeton ; une ressource d'une autre organisation donne 404 ; un test paramétré couvre automatiquement chaque route.
8. **Aucun droit d'offre codé en dur** : tout passe par le module `entitlements`.
9. **Journaux** : masquage par sous-chaîne de clé et par motif, y compris dans les exceptions ; aucune query string sur les routes de vote.
10. **Dépôt public** : aucun secret ; les trois secrets sont obligatoires et différents.
11. **Référence ToneVote** : comportement seulement. Ni code, ni nom, ni marque, ni palette, ni textes, ni URL.
12. **Interface en français** ; code, identifiants et commits en anglais.

## 4. État au moment de la relance
- **Lot 0** en cours, livré en 7 blocs :
  - blocs 1 (racine et docs) et 2 (Docker et CI) : produits et **corrigés**. La version de référence de ces fichiers est décrite dans `lot0-01` et `lot0-02` ;
  - bloc 3 (core et db) : **partie a produite, à corriger**. La liste exhaustive des corrections est dans `lot0-03-core-db.md`, `lot0-05-auth-api.md` et `vote-transaction.md`. Points principaux :
    - `pyproject.toml` : `pymongo` sans extras, plus `email-validator` ; `[dependency-groups]` au lieu de `[tool.uv] dev-dependencies` ; `asyncio_default_test_loop_scope` ; tous les marqueurs ; ne pas exclure `seed.py` de la couverture ;
    - `config.py` : `SIGNUP_ENABLED` faux par défaut en production ; `env_file=None` ; refus de l'URI par défaut en production ; `MONGO_SLOWMS` ;
    - `logging.py` : masquage par sous-chaîne de clé (dont `cookie`), récursif sur les listes, **appliqué aux exceptions** ; horodatage ISO UTC ; middleware de journaux d'accès sans query string ;
    - `security.py` : `verify_password` qui capture toutes les erreurs argon2 ; hachage factice contre l'énumération ; liste de mots de passe d'au moins 10 000 entrées, licence citée, démarrage en échec si elle est absente ; revendications JWT obligatoires ; CSRF refusé si vide ;
    - identité : `normalize_email` dans `app/core/identity.py`, identités typées, et `compute_credential_fingerprint` qui normalise elle-même (préfixes `email:` et `pid:`) ;
    - `client.py` : **`run_in_transaction` basé sur `session.with_transaction`** (boucle maison supprimée), règles du callback, tests `failCommand` avec `enableTestCommands=1` en test uniquement ;
    - schémas : `participant_links` et `auth_tokens` complets (voir « Schémas particuliers ») ; `additionalProperties: false` à **chaque niveau**, `patternProperties` pour `usage`, `items` pour chaque tableau ; tests de rejet à la racine, dans un sous-objet et dans un élément de tableau.
  - blocs 3b (schémas, index, migrations, `main.py`, seed, export OpenAPI), 4, 5, 6 et 7 : à produire.
- **Lots 1 à 5** : à faire, dans l'ordre de la section 14 de `PROMPT_MVP.md`.

## 5. Méthode de travail
- **Un lot à la fois.** Ne commence pas un lot avant la validation explicite de Fred.
- Le lot 0 se livre **par blocs** (1 à 7, le bloc 3 peut être découpé en 3a et 3b). Annonce le nombre de blocs au départ.
- **Chaque bloc** :
  - fichiers **complets** avec leur chemin, jamais d'extraits ni de « reste inchangé » ;
  - **avant** de produire, relis la spécification du bloc dans `docs/architecture/` et vérifie chaque exigence ;
  - **à la fin**, une liste de contrôle « exigence → fichier » pour les points de la spécification.
- **Fin de lot** :
  - arborescence complète ;
  - message de commit au format Conventional Commits ;
  - mise à jour de `docs/CHANGELOG.md` (livré, ouvert, reporté) ;
  - nouvelles décisions dans `DECISIONS.md` ;
  - procédure de vérification locale avec le résultat attendu de chaque commande ;
  - rapport de couverture.
- Si tu ne peux pas exécuter le code, écris **« code non exécuté »** en tête de la livraison, et privilégie des tests qui tournent sans infrastructure pour les modules purs.
- **Versions** : vérifie chaque version et chaque SHA d'action avant de les écrire, et consigne-les dans D012. N'affirme pas un fait externe (date de fin de support, dépréciation) sans le vérifier et le sourcer.
- **Questions** : regroupe-les en une seule fois, au début du bloc, avec ta proposition par défaut pour chacune.

## 6. Première action attendue
1. Confirme en 10 lignes maximum que tu as lu les sources :
   - le lot et le bloc où tu reprends ;
   - les 3 règles d'anonymat qui te semblent les plus exposées dans ce bloc ;
   - les questions éventuelles.
2. Livre ensuite les **corrections du bloc 3a**, puis le **bloc 3b**.
