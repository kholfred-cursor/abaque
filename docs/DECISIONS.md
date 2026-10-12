# Décisions techniques

Chaque décision prise en dehors de `PROMPT_MVP.md`, ou qui la précise, est consignée ici. Format : contexte, décision, conséquences, source si un fait externe est cité. Une décision n'est jamais supprimée : elle est remplacée par une nouvelle entrée qui la référence.

## D001 — PyMongo async au lieu de Motor
- **Contexte** : MongoDB annonce Motor déprécié au 14 mai 2026 et recommande l'API asynchrone de PyMongo. Source : https://www.mongodb.com/docs/languages/python/pymongo-driver/reference/migration/
- **Décision** : `pymongo` (`AsyncMongoClient`), sans extras inutiles. Motor est interdit (test d'architecture).
- **Conséquences** : un seul client par boucle d'événements, créé dans le `lifespan` ; `find()` renvoie un `AsyncCursor` ; `to_list(None)` ; pas de `io_loop` ni de `connect` ; WeasyPrint dans `run_in_executor` sur des données déjà extraites ; transactions via `session.with_transaction`.

## D002 — React 19
React 19, React Router 7 en mode bibliothèque, TypeScript strict.

## D003 — Node 24 LTS
- **Contexte** : Node 20 est en fin de vie depuis le 30 avril 2026. Source : https://endoflife.ai/nodejs/20
- **Décision** : Node 24, image `node:24-alpine`, `.nvmrc` à 24, `engines.node >= 24`.

## D004 — Vite 8
- **Contexte** : Vite n'a pas de version LTS ; la 6.4 ne reçoit plus que des correctifs de sécurité. Source : https://vite.dev/releases
- **Décision** : Vite 8. Repli possible sur la 7.3, à consigner ici si un plugin l'impose.

## D005 — Python 3.13
- **Contexte** : la branche 3.12 ne reçoit plus que des correctifs de sécurité.
- **Décision** : Python 3.13, image `python:3.13-slim`. Passage à la 3.14 possible quand toutes les dépendances, WeasyPrint compris, la supportent.

## D006 — MongoDB 7.0
- **Décision** : `mongo:7.0` pour le MVP. Fin de support **à vérifier et à documenter ici avec sa source**. Le passage à 8.0 est une décision manuelle (Dependabot ignore les montées majeures de l'image `mongo`).

## D007 — Pas de segmentation par e-mail
Aucun type e-mail dans les questions de segmentation, quel que soit le mode. Écart assumé avec le cahier des charges initial. Seules les questions fermées et les tranches numériques sont des segments ; le texte libre est stocké dans `general_answers`.

## D008 — `credential_uses` sans aucun lien vers le bulletin
Collection séparée, qui contient le fingerprint, `key_id` et la date au jour près, **sans `ballot_id` ni heure**. Fingerprint `HMAC-SHA256(CREDENTIAL_HMAC_KEY, "v1|version_id|identité")`, **indépendant du jeton**. Aucune rotation de clé tant qu'une version est ouverte.

## D009 — Pas de modification du vote après envoi
Hors MVP : cela exigerait un lien de retour vers le bulletin.

## D010 — Facturation en ligne hors MVP
Le changement d'offre se fait à la main par le super-administrateur.

## D011 — Licence propriétaire provisoire
« Tous droits réservés », titulaire à compléter par Fred.

## D012 — Outillage et épinglage
- uv : même version dans le Dockerfile (`ghcr.io/astral-sh/uv:<version>`) et dans la CI (`astral-sh/setup-uv` avec `version:`). Les deux emplacements évoluent ensemble.
- Actions GitHub épinglées par SHA vérifié contre leur tag.
- `uv.lock` et `package-lock.json` commités ; images Docker à version précise ; Dependabot (uv, npm, docker, docker-compose, github-actions), mineures groupées, majeures séparées.
- Versions exactes retenues au lot 0 : *à compléter par l'agent*.
- Le `mongod` de **test** (Docker Compose de test et CI) est lancé avec `--setParameter enableTestCommands=1`, pour les tests `failCommand` de `run_in_transaction`. **Jamais en production.**

## D013 — Un seul worker uvicorn
- **Contexte** : la limite de débit est en mémoire et APScheduler tourne dans l'API.
- **Décision** : 1 worker. Le démarrage échoue si `WEB_CONCURRENCY > 1` avec `RATE_LIMIT_BACKEND=memory`.
- **Conditions de levée** : limite de débit partagée, scheduler sorti de l'API, tâches planifiées idempotentes (cette dernière exigence s'applique dès maintenant).

## D014 — Monorepo unique
`backend/`, `frontend/`, `docs/`, sans outil de monorepo. Contrat OpenAPI : `schema.d.ts` commité et comparé en CI.

## D015 — Authentification animateur maison
Pas de fournisseur d'identité externe. Access JWT HS256 de 15 min et refresh token opaque de 14 jours (haché, rotatif, révocation globale en cas de réutilisation), dans des cookies `HttpOnly`. CSRF par double-submit. argon2id. Pas de liste de révocation des access tokens : 15 min de validité résiduelle au plus après une déconnexion globale.

## D016 — Dates et identifiants du domaine vote en chaînes
- **Contexte** : un validateur `$jsonSchema` ne peut vérifier ni l'absence d'heure dans un type `date`, ni le contenu d'un UUID binaire.
- **Décision** : dates des domaines vote et identité en chaîne `YYYY-MM-DD` validée par motif ; `_id` du domaine vote en chaîne UUID v4 validée par motif.
- **Exception** : `participant_links.expires_at` est de type `date`, car l'index TTL l'exige. Le document est supprimé à l'usage (`find_one_and_delete`) ou à l'expiration, ne porte ni `used_at` ni `created_at`, et ne contient aucune donnée de vote.
- **Corollaire** : `additionalProperties: false` à chaque niveau d'imbrication, `patternProperties` pour les clés dynamiques, schéma `items` pour chaque tableau.

## D017 — Exports séparés
Trois exports (agrégé avec segments, bulletins sans segments, textes) ; l'export individuel avec segments est interdit pour tous les rôles. Voir `docs/architecture/exports.md`.

## D018 — Limite de débit en mémoire
Fenêtre glissante en mémoire, derrière l'interface `RateLimiter`. Implique D013.

## D019 — Inscription contrôlée par `SIGNUP_ENABLED`
Vrai par défaut en développement, **faux par défaut en production** jusqu'au lot 5. Les organisations créées par inscription reçoivent `plan_code="trial"`.

## D020 — Code HTTP du dépassement d'offre
*À choisir par l'agent (402 ou 403) et à consigner ici.*

## D021 — Échelle et modes
5 couleurs (sans blanc ni noir) ; 3 modes de participation dès le MVP ; seuil k de 3, modifiable à la hausse uniquement.

## D022 — Liste de mots de passe courants
Source et licence à citer ici (par exemple SecLists, licence MIT). Au moins 10 000 entrées ; démarrage en échec si le fichier est absent ou trop court.

## D023 — Normalisation des e-mails et alias
- **Décision** : une fonction unique `normalize_email` (NFKC, `strip`, séparation sur le dernier `@`, domaine en minuscules et IDNA sans point final, partie locale en `casefold`, validation avec `email-validator`), utilisée partout où un e-mail est comparé ou stocké, et appelée **par** `compute_credential_fingerprint`. Identités typées (`EmailIdentity`, `ParticipantIdentity`) et préfixe `email:` ou `pid:` dans le message HMAC.
- **Risque accepté** : pas de suppression des alias `+tag` ni des points, qui dépendent du fournisseur. En mode ouvert, une personne peut voter plusieurs fois avec des alias. Parades : liste blanche de domaines, mode fermé. Mentionné dans le guide animateur.

## D024 — Transactions via `with_transaction` uniquement
- **Contexte** : une boucle de relance maison réexécute tout le callback après un `UnknownTransactionCommitResult`, ce qui peut créer un bulletin en double en mode anonyme.
- **Décision** : `session.with_transaction` (`majority`, `PRIMARY`). Callback sans effet de bord hors base, toutes les opérations avec `session=session`, aucune `PyMongoError` avalée, valeurs aléatoires générées dans le callback. Tests `failCommand` obligatoires.

## D025 — Jetons des animateurs (`auth_tokens`)
Consommation atomique (`used_at` posé une seule fois, `expires_at` toujours vérifié en plus du TTL), un seul jeton actif par admin et par usage, suppression des jetons `reset_password` et révocation des sessions après une réinitialisation. `magic_link_admin` est réservé et inutilisé au MVP.

## D026 — Granularité des événements d'export
- **Décision** : `version_events` enregistre un événement par export (type `export`, sous-type `aggregated`, `ballots` ou `texts`), avec l'administrateur, l'horodatage et le seuil k appliqué. Jamais de paramètres permettant de reconstituer un sous-groupe (pas de filtre de segment en clair).
- **Motif** : traçabilité des sorties de données sans créer de lien entre identité et vote.

## D027 — Versions de l'outillage front (bloc 3c)
- **Décision** : React 19.3, React Router **7** (mode bibliothèque, comme prévu), Vite 8, Vitest 5, TypeScript **5.9** et ESLint **9**, versions exactes épinglées dans `package.json` et `package-lock.json`.
- **Motif** : `typescript-eslint` n'accepte pas TypeScript 7 (borne `< 6.1`) et `openapi-typescript` exige TypeScript 5 ; `eslint-plugin-jsx-a11y` ne déclare pas encore ESLint 10. ESLint 9 est marqué obsolète par npm : à remonter dès que `jsx-a11y` supporte ESLint 10 (Dependabot le signalera).
