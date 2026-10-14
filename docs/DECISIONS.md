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
**403** avec le code `LIMIT_REACHED` et le message « Limite de votre offre atteinte. » (`FEATURE_NOT_ALLOWED` pour une fonctionnalité absente de l'offre). 402 est réservé par HTTP et mal géré par les clients.

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

## D028 — Droits stockés en surcharges, création d'organisation hors périmètre d'organisation
- **Décision 1** : le champ `organizations.entitlements` ne contient que les **surcharges** propres à l'organisation. Les droits effectifs sont recalculés à chaque lecture par `resolve(plan_code, surcharges)`. Changer `plan_code` (ou `PLAN_DEFAULTS`) s'applique donc immédiatement, sans réécrire les documents : c'est ce qui permet de « changer l'offre en un clic » (lot 5).
- **Décision 2** : `create_with_owner` est porté par `OrganizationProvisioningRepository`, repository **hors organisation** explicitement nommé (comme `AdminAuthRepository`), car à l'inscription aucune organisation n'existe encore. `OrganizationRepository` reste strictement limité à l'organisation du `TenantContext`.

## D029 — Renouvellement de session : fenêtre de tolérance et risques acceptés
- **Décision** : un jeton de rafraîchissement présenté de nouveau **moins de 10 secondes** après sa rotation lève `ConcurrentRotation` sans rien révoquer (cas bénin de deux onglets qui se rafraîchissent en même temps : le client réessaie avec le cookie posé par la requête gagnante ; l'API répondra 409 au bloc 5). Au-delà de 10 secondes, c'est un rejeu (vol probable) : `SessionReuseDetected`, et **toutes** les sessions de l'administrateur sont révoquées.
- **Motif** : sans cette fenêtre, une simple course entre deux onglets déconnectait entièrement l'utilisateur, y compris l'onglet gagnant (constaté et testé).
- **Risques acceptés (lot 0)** :
  - `create_animator` compte puis insère : deux créations simultanées peuvent dépasser `max_animators` de 1 ;
  - `AuthTokenRepository.create` supprime puis insère : deux demandes simultanées peuvent laisser deux jetons actifs pour le même usage (chacun reste à usage unique et expire).
  À reprendre si la contrainte devient stricte (compteur sur le document d'organisation dans la transaction).

## D030 — `MongoStore`, accès unique aux repositories pour l'API et les services
- **Décision** : l'API et les services reçoivent un `MongoStore` (créé dans le `lifespan`) et lui demandent leurs repositories (`store.admin_auth()`, `store.organizations(tenant)`…). Ils n'importent jamais `pymongo` ni `bson` ; le test d'architecture le vérifie (il a détecté la première version du bloc 5a qui le faisait).
- **Limite de débit** : fenêtre glissante simple (10 essais par IP et 5 par compte en 15 min), **sans délai progressif** au lot 0. Le compteur du compte est remis à zéro après une connexion réussie.
- **Accepté** : après une déconnexion, l'access token déjà émis reste valide jusqu'à 15 min (pas de liste de révocation, cf. `lot0-05`).

## D031 — Comptes : réponses neutres, exemptions CSRF, jeton préservé
- `signup` et `password/forgot` répondent **toujours 202**, que le compte existe ou non. Un e-mail déjà inscrit reçoit le message « vous avez déjà un compte » au lieu d'un lien de vérification. Le mot de passe est haché dans les deux cas, pour un temps de réponse comparable.
- **Exemptions CSRF** supplémentaires : `verify-email` et `password/reset`. Ces requêtes portent dans le corps un jeton secret à usage unique, qu'un site tiers ne peut pas connaître, et elles arrivent depuis un lien d'e-mail, sans session ni cookie CSRF.
- **Réinitialisation** : la politique de mot de passe est vérifiée **avant** de consommer le jeton (`peek` puis `consume`). Un mot de passe refusé ne fait donc pas perdre le lien. Après succès : jetons de réinitialisation supprimés et **toutes** les sessions révoquées.
- **Changement de mot de passe** : un mot de passe actuel incorrect renvoie **400 `WRONG_PASSWORD`** et non 401, pour que le front ne tente pas de rafraîchir la session ; les autres sessions sont révoquées, la session courante est conservée.
- **Sessions** : seule une description courte de l'appareil est stockée (« Firefox · Windows »), jamais l'en-tête `User-Agent` brut. Révoquer la session d'un autre administrateur renvoie 404.
- Le *slug* d'une organisation reçoit un suffixe aléatoire : il ne révèle jamais qu'un nom est déjà pris.

## D032 — Organisation des tests et découverte des routes
- **Arborescence par domaine** (`tests/core`, `db`, `entitlements`, `repositories`, `api`, `app`, `architecture`, `property`) au lieu des dossiers `unit/integration/concurrency` de `lot0-06` : un test se trouve à côté de ce qu'il vérifie. Le type reste porté par les marqueurs (`integration`, etc.). Les tests de concurrence sont dans `repositories/` et `api/`.
- **Support HTTP partagé** dans `tests/api_support.py`, chargé pour tous les tests par `pytest_plugins` (fixture `api` : application démarrée, base migrée, propriétaire connecté, mailer qui enregistre les e-mails).
- **Isolation automatique** (`tests/architecture/test_routes_tenancy.py`) : toute route dont l'arbre de dépendances contient `current_org` doit avoir une entrée dans `RESOURCE_FACTORIES`, sinon le test échoue. FastAPI 0.143 garde les routeurs inclus sous forme paresseuse (`_IncludedRouter`) : ils sont dépliés récursivement, et un test de garde échoue si la découverte ne trouve plus `/api/organization`.
- **Hypothesis** : profils `ci` (500 exemples) et `dev` (50), choisis par `HYPOTHESIS_PROFILE`.

## D033 — Comptes de démonstration en `demo.example.com`
- Les comptes de démonstration deviennent `admin@demo.example.com` et `other@demo.example.com` (mot de passe `admin`, développement uniquement). Les anciennes adresses en `.local` étaient rejetées par la validation des e-mails (`email-validator` refuse ce domaine réservé) : le compte de démonstration **ne pouvait jamais se connecter**.
- `example.com` est réservé par la RFC 2606 : aucune adresse réelle n'est concernée.
- La garde de production refuse les nouvelles adresses **et** les anciennes, au cas où une base créée avant ce changement en contiendrait encore.
- Un test de bout en bout (`tests/api/test_demo_login.py`) lance le seed puis connecte chaque compte de démonstration ; la même connexion a été vérifiée dans un vrai navigateur.

## D034 — Choix d'implémentation du front (bloc 7)
- **Aucun attribut `style`** dans le JSX : la CSP impose `style-src 'self'`. Tout passe par des CSS Modules, et une règle ESLint l'interdit.
- **Police auto-hébergée** (Atkinson Hyperlegible Next, paquet `@fontsource-variable`) : aucun appel à un CDN de polices, ce qui reste compatible avec la CSP et avec le RGPD.
- **Échelle de couleurs** : texte noir sur le vert foncé et le rouge (ni le blanc ni l'ardoise n'atteignent 4,5:1), texte ardoise sur les trois autres. Chaque couleur a un symbole distinct (`++ + ~ − −−`) : la couleur n'est jamais la seule information.
- **État d'authentification** : il vient uniquement de `GET /api/auth/me`. Rien n'est stocké dans le navigateur en dehors des cookies posés par l'API.
- **Renouvellement de session** dans le client API : sur une réponse 401, un seul `refresh` partagé entre les requêtes simultanées (204 ou 409 valent succès), puis la requête est rejouée **une fois**. Si le renouvellement échoue, l'événement `abaque:session-expired` renvoie vers `/connexion?expired=1`. Sans cookie `abq_csrf`, aucune session n'existe : le client ne tente pas de renouvellement, ce qui évite un 403 inutile à chaque visite anonyme.
- **Jetons dans l'URL** (vérification, réinitialisation) : lus une fois puis retirés de la barre d'adresse et de l'historique ; la vérification n'est envoyée qu'une seule fois, même en StrictMode.
- **Accessibilité** : erreurs annoncées (`role="alert"`) et focalisées, focus sur le premier champ invalide, cibles de 44 px, focus visible, `prefers-reduced-motion`. Le bouton « Afficher » du mot de passe garde un nom accessible fixe (« Afficher le mot de passe ») et indique son état par `aria-pressed`.
- **Cohérence entre front et backend sans dépendance** : `docs/design/scale.json` est la source commune. Le front vérifie `scale.ts` contre ce fichier, le backend vérifie `COLOR_KEYS` contre le même fichier. Le front n'importe jamais de fichier du backend, ce que vérifie le test d'architecture. Vite n'autorise en lecture hors de `frontend/` que `docs/design`.

## D035 — Le rose est conservé pour « Plutôt pas d'accord »
Question ouverte n° 1 de la spécification, tranchée par Fred au début du lot 1 : `-` reste rose (`#f0a8b8`). Il se distingue du rouge par sa clarté, et chaque couleur porte aussi un symbole.

## D036 — Lien public : slug aléatoire unique sur la plateforme
Le `slug` d'une évaluation est tiré au hasard (10 caractères parmi 32, sans `0`, `o`, `1` ni `l`). Il ne contient ni le titre ni l'organisation (section 5). Le lien `/v/:slug` doit retrouver l'évaluation sans connaître l'organisation : l'index `uq_evaluations_slug` le rend unique sur toute la plateforme, et une collision, très improbable, provoque un nouveau tirage.

## D037 — Une seule version ouverte par évaluation
Le lien public sert la version ouverte de l'évaluation. Un index unique partiel (`uq_versions_evaluation_id_open`) garantit au niveau de la base qu'il n'y en a jamais deux, même avec des ouvertures simultanées. Transitions permises : `draft → open`, `open → closed`, `closed → open` (réouverture, bulletins conservés), `draft | closed → archived` (définitif, lecture seule). Une version ouverte doit être close avant d'être archivée. Chaque transition est écrite dans `version_events` dans la même transaction. L'ouverture exige au moins un item.

## D038 — Contenu d'une version enregistré d'un bloc, avec numéro de révision
L'éditeur envoie l'ensemble des groupes, des items (dans l'ordre) et des libellés (`PUT /api/versions/{id}/content`). Le glisser-déposer, l'ajout et la suppression se font dans l'éditeur, puis un seul enregistrement remplace le contenu dans une transaction ; les identifiants existants sont conservés. Le contenu est modifiable tant que la version n'a reçu aucun bulletin et n'est pas archivée ; pour changer d'items ensuite, on duplique la version (section 9.1).
Chaque enregistrement incrémente `versions.content_revision`, et le client envoie la révision qu'il a chargée. Cela donne deux garanties : un deuxième onglet resté sur une ancienne révision reçoit 409 au lieu d'écraser le travail du premier, et l'enregistrement écrit réellement le document de la version, donc il entre en conflit dans MongoDB avec un premier bulletin simultané (qui incrémente `ballot_count` sur le même document) : jamais d'items modifiés sous un bulletin.

## D039 — Brouillon local du votant
Exception unique à l'interdiction du stockage navigateur : `frontend/src/vote/draft.ts` conserve les réponses en cours (couleurs et commentaires) pour survivre à un rechargement (section 9.4). Une clé par version ; le brouillon est effacé après un envoi accepté et reste lisible si l'envoi est refusé. Risque documenté : sur un appareil partagé, une autre personne pourrait lire un brouillon non envoyé.

## D040 — Vote anonyme livré au lot 1
Le lot 1 livre le service de vote pour le seul mode anonyme (étapes 1, 3 et 5 de la section 7) ; le lot 2 le généralise aux trois modes. Le cookie anti double vote est aléatoire, `httpOnly`, limité au chemin de l'évaluation, et ne contient aucune donnée ; le serveur ne le conserve pas. L'adresse IP ne sert qu'à la limite de débit, hachée avec `IP_HASH_SALT`, en mémoire, et oubliée à la clôture de la version.

## D041 — Détection des textes identifiants et seuil k global dès le lot 1
L'export 2 et les commentaires existent dès le lot 1 : la détection (section 11) et le seuil k global sont donc livrés maintenant dans `app/anonymity`. Le lot 2 complète ce module (sous-groupes, compléments, tests de propriétés).

## D042 — Évaluation « active » pour le quota
`max_active_evaluations` compte les évaluations qui ont au moins une version non archivée : archiver la dernière version libère la place. La création incrémente le compteur d'usage mensuel de l'organisation dans la même transaction ; deux créations simultanées entrent donc en conflit, et le quota est exact.

## D043 — Seul le mode anonyme au lot 1
Les modes `auth_open` et `auth_closed` sont refusés à la création (400 `MODE_NOT_AVAILABLE`) jusqu'au lot 3, qui livre les participants et les liens d'accès.
