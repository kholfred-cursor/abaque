# Prompt de build — Abaque (MVP SaaS)

> Ce fichier vit dans `docs/PROMPT_MVP.md` du monorepo `kholfred-cursor/abaque`. C'est la **seule référence** du projet : il remplace toutes les versions, tous les résumés et tous les échanges antérieurs, et l'emporte en cas d'écart. Toute modification du cadrage passe par une mise à jour de ce fichier, dans le même commit que le code concerné.


> **Documents liés** (à lire avec ce fichier) : `docs/architecture/` (spécifications techniques détaillées du lot 0 et des garanties), `docs/DECISIONS.md` (D001 à D025), `docs/adr/0001-stack.md`. En cas d'écart, ce fichier l'emporte ; toute modification est reportée dans les fichiers concernés, dans le même commit.
---

## 0. Rôle et règles de travail

Tu es le développeur principal d'**Abaque**, un SaaS d'évaluation collective fondé sur l'**abaque de François Régnier**. Tu travailles pour Fred, CTO et développeur full stack, seul sur le projet.

1. **Ne jamais inventer une exigence.** Si un point manque, pose la question ou choisis l'option la plus simple, puis consigne-la dans `docs/DECISIONS.md`.
2. **Avancer par lots** (section 14). Ne commence pas un lot avant que Fred ait validé le précédent.
3. **Livraison de chaque lot** :
   - une arborescence complète, prête à copier à la racine du dépôt, sans extrait partiel ni « reste inchangé » ;
   - un message de commit au format Conventional Commits ;
   - la mise à jour de `docs/CHANGELOG.md` ;
   - une procédure de vérification locale, avec le résultat attendu de chaque commande ;
   - le rapport de couverture des tests.

   Si tu ne peux pas exécuter le code, écris **« code non exécuté »** en tête de la livraison. Fred pousse sur `main` après des tests verts chez lui.
4. **Le dépôt est public.** Aucun secret dans le code : tout passe par des variables d'environnement documentées dans `.env.example`.
5. **Une référence n'est pas du code à copier.** Le prototype ToneVote illustre des comportements. N'en reprends ni le code, ni le nom, ni la marque, ni la palette, ni les textes, ni aucune URL.
6. **L'interface est en français.** Le code, les identifiants et les commits sont en anglais.

---

## 1. Produit

Un animateur crée une **évaluation**, c'est-à-dire une série d'affirmations appelées *items*. Les participants votent sur chaque item avec une **couleur**, du « tout à fait d'accord » au « pas du tout d'accord », et peuvent commenter. L'animateur obtient des **matrices triées** qui montrent le consensus et le dissensus, des **histogrammes** et des **exports protégés**.

**Problème résolu** : les sondages moyennisent, les votes binarisent, les tours de table inhibent. L'abaque rend visibles la nuance, le consensus, le dissensus et l'argumentation.

**Utilisateurs**
- **Animateur** (`owner` ou `animator`) : consultant, facilitateur, DRH, RSE, collectivité, organisme de formation. Interface pensée pour le bureau.
- **Participant** : vote surtout sur mobile, via un QR code ou un lien. Interface mobile-first.
- **Super-administrateur plateforme** (Fred) : gère les organisations clientes et leurs offres, **sans accès** à leurs résultats.

**Modèle économique** : SaaS loué par abonnement à des organisations, avec une **version démo**. Les prix seront fixés plus tard. **Aucune limite ni fonctionnalité liée à une offre n'est codée en dur** : tout passe par les droits de l'organisation (section 5).

**Objectif de la V1** : un MVP multi-organisations, pilotable en séance réelle avec un premier client, accompagné d'une démo. Les panels comptent de 10 à 300 participants. Application web uniquement, sans application native.

**Reproduction** : on reproduit les principes, les parcours et les résultats. La marque, les textes, le design et le code sont propres au projet.

---

## 2. Garantie d'anonymat (formulation contractuelle)

Ce texte s'applique à l'interface, à la politique de confidentialité, aux CGU et au DPA. Il est **interdit** d'écrire « anonymat total » ou « impossible à relier ».

> **Garantie technique** : aucune donnée applicative ne relie directement un bulletin à l'identité d'un participant. Il n'existe ni clé, ni référence, ni identifiant, ni empreinte commune entre le domaine identité et le domaine vote, et aucune vue, aucun export ni aucune API ne permet une telle jointure.
> **Protections contre la réidentification statistique** : seuil k sur les sous-groupes et leurs compléments, minimisation des métadonnées, exports individuels sans segments. Ces mesures réduisent fortement le risque de recoupement contextuel sans pouvoir l'exclure totalement, par exemple face à une personne qui connaîtrait déjà le profil ou les opinions d'un participant.

**Risques résiduels documentés** (ADR, DPA et guide animateur) :
- **Homogénéité** : si tous les bulletins d'un segment d'au moins k personnes portent la même couleur, appartenir à ce segment révèle le vote. Conseil donné à l'animateur : éviter les segments très petits ou homogènes. Pas de masquage supplémentaire au MVP.
- **Infrastructure** : l'oplog MongoDB et les sauvegardes conservent groupées les opérations d'une même transaction (section 4).

---

## 3. Monorepo et environnement de développement

**Monorepo unique**, sans outil dédié (ni Nx ni Turborepo) :

```
abaque/
├── backend/
│   ├── app/{api,domain,services,vote_engine,anonymity,entitlements,
│   │        repositories,db/schemas,jobs,core}
│   │   (db/ contient aussi indexes.py et migrations.py)
│   ├── tests/{unit,property,concurrency,integration,architecture}
│   ├── pyproject.toml   Dockerfile
├── frontend/
│   ├── src/{vote,admin,restitution,platform,shared}
│   │   (shared/ contient les tokens de design, les composants et le client API)
│   ├── package.json   tsconfig.json   vite.config.ts   Dockerfile
├── docs/{PROMPT_MVP.md,DECISIONS.md,CHANGELOG.md,adr/,samples/}
├── docker-compose.yml   .env.example   .gitignore   README.md   LICENSE
└── .github/workflows/ci.yml
```

- Le front **n'importe jamais** de code backend. Le seul lien entre les deux est le contrat **OpenAPI** (`openapi-typescript` et `openapi-fetch`). La CI échoue si les types ne sont pas à jour.
- Licence : propriétaire (« Tous droits réservés »), en attendant une décision de Fred.

**Docker Compose de développement** :
- `mongo` : `mongo:7`, `--replSet rs0 --bind_ip_all`, volume nommé, healthcheck. **Réplica set à un seul nœud.** Trois nœuds en local ne servent à rien : un nœud suffit pour les transactions.
- `mongo-init` : exécution unique et idempotente de `rs.initiate({_id:"rs0", members:[{_id:0, host:"mongo:27017"}]})`, après que `mongo` est déclaré sain.
- `api` : FastAPI (uvicorn avec rechargement), démarre après `mongo-init`. Au démarrage, il applique les migrations (validateurs et index), puis le seed si `SEED_DEMO=true`.
- `web` : Vite avec HMR, proxy `/api` vers `api:8000`. Le front et l'API partagent ainsi le même domaine.
- URI : `mongodb://mongo:27017/abaque?replicaSet=rs0` (avec `directConnection=true` pour un client lancé hors de Docker).

Commandes du README :
- `docker compose up` : tout démarre ;
- `docker compose exec api pytest` : tests backend ;
- `docker compose down -v` : remise à zéro complète.

**CI GitHub Actions** : jobs `backend` (ruff, mypy strict, pytest avec couverture, MongoDB en réplica set mono-nœud), `frontend` (eslint, `tsc --noEmit`, vitest, build) et `contract` (vérification des types OpenAPI), déclenchés selon les chemins modifiés. Un job `e2e` (Playwright) tourne sur `main` à partir du lot 1.

**Production** : réplica set à 3 nœuds, ou Atlas en région UE. Seule l'URI change. **Un seul worker uvicorn** derrière nginx (même domaine, proxy `/api` sans barre finale, en-têtes de sécurité dans chaque `location`, CSP stricte), tant que la limite de débit est en mémoire (D013, `docs/architecture/production.md`).

---

## 4. Stack imposée et ADR 0001

La stack est **fixée par l'environnement de réalisation**. L'ADR ne la choisit pas : il la documente.

| Couche | Choix |
|---|---|
| Front | React 19, TypeScript strict, Vite 8, React Router 7, client typé depuis l'OpenAPI (`openapi-typescript` + `openapi-fetch`), Node 24 LTS |
| Back | Python 3.13, FastAPI, Pydantic v2, pydantic-settings, PyJWT, argon2-cffi ; dépendances verrouillées (`uv.lock`) |
| Base de données | MongoDB 7+ via l'**API asynchrone native de PyMongo** (`pymongo.AsyncMongoClient`, version 4.x récente épinglée). **Motor est interdit** : MongoDB l'a déprécié au 14 mai 2026. Base hébergée dans l'UE, de préférence en France |
| Tâches planifiées | APScheduler : purges, rappels, remise à zéro de la démo, fin d'essai |
| PDF / CSV | Générés côté serveur (WeasyPrint), uniquement à travers `anonymity` |
| E-mail | Interface `Mailer` : implémentation console au lot 0, fournisseur européen ensuite |

**Exclus** : OAuth et réseaux sociaux, websockets (polling de 5 à 10 s), analyse sémantique des commentaires, fournisseur d'identité externe.

### Contenu attendu de `docs/adr/0001-stack.md`
1. **Contexte** : MongoDB est une contrainte d'environnement, alors que le modèle est relationnel. Les garanties critiques reposent sur l'unicité, l'atomicité et le k-anonymat.
2. **Garde-fous obligatoires** :
   - réplica set partout ;
   - validateurs `$jsonSchema` en `strict` / `error`, avec **`additionalProperties: false`** (liste blanche des champs) ;
   - index uniques (section 6) et transactions `majority` via **`session.with_transaction`** de PyMongo (pas de boucle de relance maison, qui pourrait dupliquer un bulletin après `UnknownTransactionCommitResult`) ;
   - identifiants UUID v4 dans le domaine vote, jamais d'ObjectId (qui contient l'heure de création) ;
   - dates du domaine vote sous forme de **chaîne `YYYY-MM-DD`** (section 6.5) ;
   - isolation par `organization_id` dans les repositories ;
   - séparation des domaines identité et vote.
3. **Couche repository = voie de migration vers PostgreSQL.** Le domaine dépend d'interfaces (protocoles Python). `vote_engine`, `anonymity` et `entitlements` sont du Python pur. Migrer reviendrait à réécrire les repositories, à remplacer les validateurs par des contraintes SQL, puis à rejouer les mêmes tests.
4. **Compromis et risques résiduels** :
   - garanties moins lisibles qu'en SQL, compensées par les validateurs et les tests ;
   - agrégations faites dans `vote_engine`, pas dans des pipelines `$group` ;
   - oplog et sauvegardes : taille d'oplog minimale, accès réservé à l'exploitation, sauvegardes chiffrées à rétention courte, mention dans le DPA et le registre ;
   - profiler MongoDB désactivé, seuil `slowms` élevé en production, aucune journalisation applicative des requêtes complètes sur les routes de vote ;
   - risque d'homogénéité (section 2).
5. **Critères de réévaluation** : audit externe qui exige des garanties SQL, plus de 10 000 bulletins par version, ou changement d'environnement.

---

## 5. SaaS : organisations, droits, démo, RGPD

**Isolation multi-organisations (non négociable, dès le lot 0)**
- Chaque document métier porte une `organization_id`, y compris dans le domaine vote, où ce champ n'identifie personne.
- Le repository injecte toujours l'`organization_id` issue du jeton de session, **jamais** celle envoyée par le client.
- Les opérations de plateforme (super-administrateur) passent par des repositories `platform_*` distincts, qui n'ont accès ni au domaine vote ni au domaine identité.
- Aucun accès direct à une collection hors de `repositories/` et `db/`.
- Les jetons, les slugs publics et les QR codes ne révèlent pas l'organisation.

**Droits (`entitlements`)** : module Python pur, unique point de vérification côté serveur (`check()` et `get_limit()`). Valeurs par défaut par `plan_code` dans un fichier de configuration ; l'interface se contente d'afficher ce que le serveur autorise.

Clés :
- `max_active_evaluations`, `max_ballots_per_version`, `max_animators` ;
- `modes_allowed` ;
- `pdf_export`, `csv_export`, `email_invitations`, `custom_branding` ;
- `retention_months`.

Le dépassement d'une limite affiche « Limite de votre offre atteinte ». La limite de bulletins est vérifiée **dans** la transaction de vote (section 7). Des compteurs d'usage mensuels sont tenus : évaluations, bulletins, e-mails.

**Inscription en libre-service** : contrôlée par `SIGNUP_ENABLED`, désactivée par défaut en production jusqu'au lot 5. Une organisation créée par inscription reçoit `plan_code = "trial"`.

**Démo** *(périmètre exact à confirmer)*
- **Démo publique** : une évaluation d'exemple aux résultats fictifs, remise à zéro chaque nuit.
- **Compte d'essai** : inscription libre avec vérification de l'e-mail. Limites indicatives : 1 évaluation, 30 bulletins, 14 jours. Filigrane « Démo » sur le PDF. À la fin de l'essai, l'organisation passe en lecture seule 30 jours, puis elle est purgée, avec un e-mail d'avertissement.

**Super-administrateur** : liste les organisations, change leur offre, les suspend. TOTP obligatoire (lot 5). **Aucune route** ne lui donne accès aux résultats ou aux exports des clients. La facturation en ligne est hors MVP : le changement d'offre se fait à la main.

**RGPD** : le client est responsable de traitement, l'éditeur est sous-traitant (article 28). Modèles de CGU, de DPA, de registre des sous-traitants ultérieurs et de politique de confidentialité au lot 5.

---

## 6. Modèle de données

Trois domaines. Entre le domaine identité et le domaine vote, **le seul point de contact est `version_id`**. Toutes les collections sont créées, avec leur validateur, **dès le lot 0**.

### 6.1 Plateforme et contenu
```
organizations     _id, name, slug, plan_code, status (active|suspended|deleted),
                  entitlements{}, usage{YYYY-MM:{...}}, trial_ends_at?, created_at
admins            _id, organization_id?, email, email_verified, password_hash,
                  role (owner|animator|superadmin), totp_secret_enc?, created_at
admin_sessions    _id, admin_id, token_hash, expires_at, revoked_at?, user_agent_hint?
auth_tokens       _id, admin_id, purpose (verify_email|reset_password|magic_link_admin),
                  token_hash, expires_at, used_at?   -- jetons animateurs ; magic_link_admin
                                                     -- réservé, inutilisé au MVP
evaluations       _id, organization_id, admin_id, title, description, language, logo_url?,
                  participation_mode (anonymous|auth_open|auth_closed),
                  allowed_email_domains[]?, access_code_hash?, slug,
                  vote_preset (agreement|score|custom), intro_md?, outro_md?,
                  show_vote_example, anonymity_threshold (≥3), settings{}
versions          _id, organization_id, evaluation_id, label,
                  status (draft|open|closed|archived), is_visible,
                  ballot_count, credential_key_id?, closed_at?, purge_at?
version_events    _id, organization_id, version_id,
                  kind (opened|closed|reopened|archived|export_generated|
                        reminder_sent|purged), at, admin_id
item_groups, items, color_labels, glossary,
segment_questions (type single|multiple|text|number ; options[]? ; number_buckets[]?),
general_questions
```

### 6.2 Identité (qui ?)
```
participants      _id, organization_id, version_id, email?, first_name?, last_name?,
                  trigram?, groups[], token_hash?, has_voted, invited
participant_links _id, organization_id, version_id, email_normalized, token_hash,
                  expires_at (date, pour le TTL)  -- liens magiques du mode ouvert (lot 3) ;
                                                  -- supprimés à l'usage, ni used_at ni created_at
credential_uses   _id, organization_id, version_id, credential_fingerprint, key_id,
                  consumed_on ("YYYY-MM-DD")
email_logs        _id, organization_id, version_id, participant_id, kind,
                  sent_on ("YYYY-MM-DD"), status
```

### 6.3 Vote (quoi ?), avec `_id` en UUID v4 sous forme de chaîne
```
ballots           _id, organization_id, version_id, submitted_on ("YYYY-MM-DD"),
                  groups[] (mode fermé uniquement), rand_key
votes             _id, organization_id, ballot_id, item_id,
                  color_key (++|+|~|-|--), comment?, comment_status (published|hidden|flagged)
segment_answers   _id, organization_id, ballot_id, question_id, option_ids[]? | bucket?
general_answers   _id, organization_id, ballot_id, question_id, text, comment_status
```
Le texte libre d'une question de segmentation de type `text` est stocké dans `general_answers`. Il n'est donc jamais utilisable comme segment.

### 6.4 Index
- Uniques : `organizations(slug)`, `admins(email)`, `auth_tokens(token_hash)`, `admin_sessions(token_hash)`, `evaluations(organization_id, slug)`, `participant_links(token_hash)`, `credential_uses(version_id, credential_fingerprint)`, `votes(ballot_id, item_id)`, `segment_answers(ballot_id, question_id)`, `general_answers(ballot_id, question_id)`.
- Uniques partiels : `participants(version_id, email)` (si `email` existe) et `participants(token_hash)` (si `token_hash` existe).
- Simples : `ballots(version_id, rand_key)`, plus tous les champs `organization_id`.
- Index TTL : `auth_tokens(expires_at)` et `participant_links(expires_at)`.

### 6.5 Règles strictes sur les données
- **`additionalProperties: false` à chaque niveau d'imbrication**, `patternProperties` pour les clés dynamiques (`usage` : `^\\d{4}-\\d{2}$`), et un schéma `items` pour chaque tableau.
- **Dates du domaine vote et du domaine identité stockées en chaîne `YYYY-MM-DD`**, validées par `pattern: "^\\d{4}-\\d{2}-\\d{2}$"`. Un validateur `$jsonSchema` ne sait pas vérifier l'absence d'heure dans un type `date` : seule une chaîne permet de garantir la précision au jour **au niveau de la base**.
- **`_id` du domaine vote** : chaîne UUID v4 validée par `pattern: "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"`.
- Domaine vote : `additionalProperties: false`, et **aucun** `participant_id`, e-mail, jeton, fingerprint ou dérivé, ni dans les documents, ni dans les journaux, ni dans les exports.
- **Aucun horodatage automatique** dans le domaine vote : pas de `created_at` ni `updated_at`.
- `participants` ne contient aucune date de vote, seulement `has_voted`.
- Les questions de type nombre ne stockent que la tranche (`bucket`), jamais la valeur brute.
- `ballots.groups[]` ne contient que les noms de groupes recopiés au vote, en mode fermé, et n'est lu qu'à travers `anonymity`.
- **Exception** : `participant_links.expires_at` est de type `date`, parce que l'index TTL l'exige. Le document est supprimé à l'usage ou à l'expiration et ne contient aucune donnée de vote.
- `rand_key` est un nombre aléatoire tiré à la création. Il fixe l'ordre aléatoire stable de la version, et aucune lecture n'utilise l'ordre d'insertion.

---

## 7. Écriture d'un vote et `credential_uses`

### Fingerprint
`HMAC-SHA256(CREDENTIAL_HMAC_KEY, "v1|" + version_id + "|" + kind + ":" + identité_stable)`, encodé en hexadécimal, avec `kind` égal à `email` ou `pid`. La normalisation est faite **dans** la fonction de calcul.
- **Authentifié ouvert** : `identité_stable` est l'e-mail normalisé par `normalize_email` (NFKC, `strip`, domaine en minuscules et IDNA, partie locale en `casefold`), vérifié par lien magique. Les alias `+tag` et les points ne sont **pas** supprimés : risque de double vote accepté en mode ouvert (D023).
- **Authentifié fermé** : l'e-mail normalisé s'il existe, sinon le `participant_id`. **Jamais le jeton**, sinon régénérer le jeton permettrait de revoter.
- **Anonyme** : `credential_uses` n'est pas utilisé.
- `CREDENTIAL_HMAC_KEY` est une clé dédiée, identifiée par `key_id` (empreinte courte et non réversible de la clé). **Aucune rotation tant qu'une version est ouverte** : le démarrage échoue si la clé a changé alors qu'une version `open` existe.
- L'import de participants avec « remplacer l'existant » est **interdit** dès qu'une version a reçu un bulletin. Seul l'ajout reste possible.

### Transaction (`session.with_transaction`, `majority`)
1. **Verrou d'ouverture et quota en une seule écriture** :
   `versions.update_one({_id, organization_id, status:"open", ballot_count:{$lt:max}}, {$inc:{ballot_count:1}})`.
   - Si aucun document n'est modifié, on détermine la raison (version close ou limite atteinte), puis on annule.
   - Cette écriture provoque un conflit avec une clôture concurrente : une simple lecture du statut ne suffirait pas.
2. **Modes authentifiés** : insérer `credential_uses`. En cas de clé dupliquée, renvoyer le code 409 « Votre vote a déjà été enregistré » et annuler.
3. Insérer `ballots`, `votes`, `segment_answers` et `general_answers`. La détection des données identifiantes positionne `comment_status` (section 11).
4. **Modes authentifiés** : `participants.has_voted = true`. En mode fermé, invalider `token_hash`.
5. Valider la transaction. La réponse ne contient **aucun** identifiant de bulletin.

**Mode anonyme** : étapes 1, 3 et 5. Un cookie aléatoire limite le double vote par navigateur. L'adresse IP, utilisée seulement pour limiter le débit, est hachée avec `IP_HASH_SALT` et purgée à la clôture.

**Cas d'erreur** :
- `UnknownTransactionCommitResult` : on relance la validation. Si l'essai suivant rencontre une clé dupliquée, on renvoie le même message neutre « Votre vote a déjà été enregistré ».
- Pas de clé d'idempotence fournie par le client.
- Le `credential_use` d'un participant supprimé est conservé jusqu'à la purge de la version.
- **Modification du vote après envoi** : non autorisée dans le MVP.

---

## 8. Authentification

### Animateurs (lot 0)
- Pas de fournisseur d'identité externe : utilisateurs dans `admins`.
- Mots de passe en **argon2id**, 12 caractères minimum, vérification contre une liste de mots de passe courants. **Cette politique s'applique à toutes les routes de l'API.** Seul le seed de développement peut la contourner (pour `admin`), jamais l'API.
- **Access token** : JWT HS256 (`JWT_SECRET`), durée de 15 min. Contenu : `sub`, `organization_id`, `role`, `exp`, `jti`. Aucune donnée personnelle.
- **Refresh token** : chaîne opaque de 256 bits, durée de 14 jours, stockée hachée dans `admin_sessions`.
  - Rotation à chaque utilisation.
  - Réutilisation d'un refresh token déjà consommé : révocation de toutes les sessions de l'utilisateur.
- Les deux jetons sont envoyés dans des cookies **`httpOnly`, `SameSite=Lax`**, et `Secure` selon `COOKIE_SECURE` (`true` en production, `false` en développement http). Rien n'est stocké dans le `localStorage`.
- **CSRF** par double-submit (en-tête `X-CSRF-Token`) sur toutes les routes qui modifient des données.
- Vérification de l'e-mail et réinitialisation du mot de passe par jetons à usage unique stockés hachés dans `auth_tokens` (réinitialisation : 30 min). Page « Mes sessions ».
- **Limite de débit** avec délai progressif sur la connexion, par IP hachée et par compte. Stockage en mémoire au MVP (une seule instance d'API), consigné dans `DECISIONS.md`. Message d'erreur générique, qui ne révèle pas si un compte existe.
- Dépendances FastAPI : `current_admin`, `current_org`, `require_role`.
- Super-administrateur : TOTP obligatoire au lot 5. Lien magique animateur hors MVP.

### Participants (lot 3)
- **Mode ouvert** : lien magique à usage unique (15 min, collection `participant_links`), qui ouvre une session de vote limitée à la version. Liste blanche de domaines e-mail optionnelle. Ce mécanisme est séparé de l'authentification animateur.
- **Mode fermé** : jeton de 128 bits au moins, stocké haché, transmis par lien ou QR code nominatif, régénérable (l'ancien est alors invalidé), avec la mention « Lien personnel, ne pas transférer ».
- **Code d'accès** optionnel, stocké haché.

### Secrets et configuration
- `JWT_SECRET`, `CREDENTIAL_HMAC_KEY` et `IP_HASH_SALT` sont obligatoires et **tous différents** : le démarrage échoue si l'un manque ou si deux sont identiques.
- Autres variables : `MONGODB_URI`, `DATABASE_NAME`, `ENVIRONMENT` (development|production), `SEED_DEMO`, `SIGNUP_ENABLED`, `COOKIE_SECURE`, `APP_BASE_URL`.
- Les journaux masquent jetons, mots de passe, adresses e-mail et fingerprints.
- `GET /health` renvoie seulement `{"status":"ok"}` publiquement. Le détail (réplica set, migrations) n'est accessible qu'en développement ou depuis le réseau interne. Le contrôle du réplica set utilise la commande `hello` (`isMaster` est obsolète).

---

## 9. Fonctionnalités

Légende : **[M]** indispensable, **[S]** souhaité si le délai le permet.

### 9.1 Évaluations et versions — [M]
- Créer, modifier, dupliquer et supprimer une évaluation. La suppression est définitive, demande une confirmation, et un export est proposé juste avant.
- **Cycle de vie d'une version** : `brouillon → ouverte ⇄ fermée → archivée`.
  - La réouverture conserve les bulletins.
  - Une version archivée est en lecture seule.
  - Les items sont figés dès le premier bulletin : pour changer d'items entre deux vagues, on duplique la version.
  - Chaque transition est journalisée.
- Menu d'administration : Évaluation → Items → Questions → Participants → Versions → Glossaire → Paramètres.

### 9.2 Contenu — [M]
- **Groupes et items** : CRUD, glisser-déposer, import et export CSV (`docs/samples/items.csv`).
- **Préréglages d'échelle** : *Accord*, *Score 1–5*, *Personnalisé*.
- **Questions de segmentation**, de quatre types : choix unique, choix multiple, texte, nombre.
  - **Aucun type e-mail.** *Cet écart avec le cahier des charges initial est consigné dans `DECISIONS.md`.*
  - Seules les questions **fermées** servent de segments et de filtres.
  - **Nombre** : seule la tranche, définie par l'animateur, est stockée et utilisée.
  - **Texte** : jamais un segment ; traité comme un commentaire.
  - L'éditeur rappelle : « Ne demandez pas d'information permettant d'identifier une personne (nom, e-mail, téléphone, matricule). »
- **Questions ouvertes générales** en fin de formulaire.
- **[S] Glossaire** : renommer « item » et les libellés de l'échelle.

### 9.3 Participants et convocations
- **[M]** Groupes, ajout manuel, import CSV (avec « remplacer l'existant » seulement avant le premier bulletin), export CSV du domaine identité uniquement (nom, e-mail, groupes, `has_voted`). L'onglet est masqué en mode anonyme.
- **[M]** Lien et QR code : publics en mode anonyme ou ouvert, nominatifs en mode fermé.
- **[S]** Convocations par e-mail : à tous, aux non-votants, à un groupe ou à une personne. Message modifiable, confirmation avant l'envoi, journalisation.

### 9.4 Parcours de vote — [M]
1. **Introduction** en markdown, bouton « Commencer », exemple d'échelle optionnel.
2. **Profil** : questions de segmentation, avec le texte de garantie abrégé.
3. **Vote** : items présentés par groupe. Chaque item affiche :
   - 5 boutons de couleur, chacun avec un symbole et un libellé ;
   - un commentaire facultatif, sous lequel s'affiche en permanence : « Ne mentionnez ni nom ni information permettant de vous identifier ou d'identifier un tiers. »
4. **Retour visuel** : la sélection est visible immédiatement et une barre de progression s'affiche, **sans modale par item**.
5. **Questions ouvertes générales.**
6. **Envoi définitif** : c'est la **seule** confirmation explicite, avec un récapitulatif des items sans réponse.
7. **Écran de fin** en markdown.

Comportements attendus :
- un item par écran ou tout sur une page ;
- navigation entre les groupes avant l'envoi ;
- utilisable sans zoom à 360 px, zones tactiles d'au moins 44 px ;
- **brouillon local** en cas de rechargement, sans mode hors-ligne : un envoi reçu après la clôture est refusé (« Cette consultation est close, votre réponse n'a pas été enregistrée »), et le brouillon reste lisible.

### 9.5 Restitution — [M]
- **Matrices** :
  - *brute*, dans l'ordre de `rand_key` ;
  - *participants*, triée par `ballotScore` ;
  - *items*, triée par score ;
  - *mixte*, les deux tris combinés.

  Chaque cellule montre sa couleur et un indicateur de commentaire cliquable. Légende, plein écran, colonne des items figée au défilement. Au-delà de 50 bulletins, une matrice agrégée remplace la matrice par colonnes.
- **Histogrammes** : général, par item, et détail d'un item ventilé par segment.
- **Filtres** combinables par groupe et par segment fermé, tous passés par `anonymity`.
- **Tableau de bord de séance** : compteurs seulement, rafraîchis par polling toutes les 5 à 10 s.
- **[S] Signaux** : consensus positif et négatif, items polarisants, items incertains, voix minoritaires.
- **Vues individuelles** (matrices brute, participants et mixte) **indisponibles** si la version compte moins de k bulletins.

### 9.6 Commentaires et modération — [M]
- Console filtrée par item, par couleur et par segment (seuil k appliqué).
- L'animateur peut masquer, republier ou tout supprimer après confirmation. Il **ne peut jamais modifier** un texte. Un rappel du cadre légal s'affiche.
- File « À modérer » alimentée par la détection automatique.
- Les textes ne sont **jamais** visibles des autres participants.

### 9.7 Exports — [M]
Voir la section 12.

### 9.8 Paramètres avancés — [S]
Mode d'affichage du vote, commentaire obligatoire, exemple d'échelle, seuil k (à la hausse uniquement), bulletins attendus. Chaque option a une aide « ? ».

---

## 10. Échelle et moteur de calcul

### Échelle (5 couleurs, sans blanc ni noir)

| Clé | Couleur | Hex | Libellé « Accord » | Poids |
|---|---|---|---|---:|
| `++` | Vert foncé | `#2e8b3c` | Tout à fait d'accord | +2 |
| `+` | Vert clair | `#7ecb4d` | Plutôt d'accord | +1 |
| `~` | Jaune | `#f5d94e` | Avis partagé, opinion mitigée | 0 |
| `-` | Rose | `#f0a8b8` | Plutôt pas d'accord | −1 |
| `--` | Rouge | `#e83030` | Pas du tout d'accord | −2 |

- Un seul fichier de **tokens de design**, partagé par le front et le PDF : couleurs, symboles, contraste AA.
- Un item non voté est affiché en gris hachuré et exclu des calculs.

### `vote_engine` (Python pur)

Pour chaque **item** :
- `counts`, `expressed` ;
- `fav = ++ + +`, `defav = - + --`, `mixed = ~` ;
- `score = 2·(++) + (+) − (−) − 2·(−−)` ;
- `favPct`, `defavPct`, `mixedPct` : pourcentages sur `expressed` ;
- `dissensus = min(fav, defav)`, `polarization = min(favPct, defavPct)`.

Signaux :
- consensus positif si `favPct ≥ 80` ;
- consensus négatif si `defavPct ≥ 80` ;
- item incertain si `mixedPct ≥ 50` ;
- voix minoritaire si le groupe est à au moins 80 % d'un côté avec exactement un vote opposé.

Pour chaque **bulletin** : `ballotScore` = moyenne des poids de ses votes exprimés.

Tris :
- **Items** : score décroissant, puis `++` décroissant, puis position.
- **Bulletins** : `ballotScore` décroissant, puis nombre de votes exprimés décroissant, puis `rand_key`.

---

## 11. Module `anonymity` (Python pur) et règles k

C'est l'**unique point de passage** entre les bulletins filtrés et toute sortie : API de restitution, console de commentaires, PDF et CSV. Les routes de restitution et les générateurs d'export n'importent jamais `repositories` directement.

- **Seuil k** : 3 par défaut, modifiable **à la hausse uniquement**, appliqué à tous les rôles.
- **Seuil global** : si la version compte moins de k bulletins, les vues individuelles et les exports 2 et 3 sont refusés, et l'export agrégé ne contient que `<k`.
- **Sous-groupe et complément** : une sélection est masquée si le sous-groupe **ou son complément** compte moins de k bulletins.
  - Le complément se calcule **dans la population filtrée**.
  - **Choix multiple** : segment « a coché X », complément « n'a pas coché X ».
  - **Absence de réponse** : segment « Non renseigné », soumis à la même règle.
- **Masquage** : l'élément reste visible, grisé, avec la mention « effectif insuffisant ». L'API renvoie un résultat vide avec le motif, jamais les données. Les textes d'un sous-groupe masqué sont masqués avec lui dans les vues filtrées et dans le PDF.
- **Pas de sur-masquage** : dans un segment d'au moins k bulletins, une couleur votée par une seule personne reste affichée (risque d'homogénéité documenté, section 2).

**Détection des données identifiantes** (à la réception de chaque texte) :
- motifs repérés : adresse e-mail, téléphone français ou international, deux mots consécutifs à majuscule initiale hors début de phrase ;
- un texte repéré passe en `flagged` : il est exclu des vues, du PDF et des exports tant que l'animateur ne l'a pas validé.

---

## 12. Exports

### Règles communes
- Générés côté serveur, **uniquement** à travers `anonymity`.
- CSV en UTF-8 avec BOM, séparateur `;`, fin de ligne CRLF.
- Neutralisation des formules : une cellule qui commence par `=`, `+`, `-`, `@` ou une tabulation est préfixée par `'`.
- Soumis à l'entitlement `csv_export`. Chaque génération est journalisée dans `version_events` (`export_generated`), sans contenu.
- Textes `hidden` et `flagged` **exclus** de tous les exports.
- Nom de fichier : `abaque_<slug>_<version>_<type>.csv`, sans date ni heure.
- **L'export individuel avec segments est interdit pour tous les rôles**, super-administrateur compris. Aucun fichier ne combine une référence de bulletin avec un segment ou un groupe.

### Export 1 — Agrégé (le seul avec segments)
- Filtres acceptés : les mêmes que dans les vues.
- **Format large** : une ligne par **item × valeur de segment**, plus une ligne « Ensemble » par item.
  `item_position ; item_short_name ; segment_question ; segment_value ; n_expressed ; n_++ ; n_+ ; n_~ ; n_- ; n_-- ; pct_fav ; pct_mixed ; pct_defav ; score`
- Si le segment **ou son complément** (dans la population filtrée) compte moins de k bulletins, toutes ses valeurs numériques valent `<k`. La ligne reste présente.
- Pour les nombres, on exporte le libellé de la tranche.

### Export 2 — Bulletins (sans segments)
- **Toujours sur l'ensemble de la version.** Un paramètre de filtre renvoie une erreur 400. Export refusé si la version compte moins de k bulletins.
- Une ligne par **bulletin × item** :
  `ballot_ref ; item_position ; item_short_name ; color_key ; color_label ; comment`
- `ballot_ref` (B001, B002…) est **attribué au hasard à chaque génération**. Il ne dérive jamais de l'UUID ni de `rand_key`.
- L'ordre des bulletins est mélangé à chaque génération ; les lignes d'un même bulletin restent groupées et triées par position d'item.
- Un item non voté donne une ligne avec la couleur vide et la mention `non exprimé`. Un commentaire masqué ou à modérer donne un champ `comment` vide, sans mention.
- Colonnes **interdites** : segment, groupe, tranche, date, `rand_key`, UUID. Pas de questions ouvertes ni de réponses de profil libres.

### Export 3 — Textes
- **Toujours sur l'ensemble de la version**, sans filtre (erreur 400 sinon). Refusé si la version compte moins de k bulletins.
- **Textes publiés uniquement**, sans colonne de statut :
  `type (commentaire|réponse_ouverte|réponse_profil_libre) ; item_short_name ou question ; color_label (commentaires seulement) ; text`
- Aucun `ballot_ref`, UUID, segment, groupe ni date. Lignes **entièrement mélangées** à chaque génération : rien ne permet de regrouper les textes d'une même personne.

### Rapport PDF
Il passe par `anonymity` et suit cet ordre :
1. titre ;
2. chiffres clés ;
3. répartition globale ;
4. matrice des items ;
5. histogrammes par item ;
6. répartition par segment (`<k` appliqué) ;
7. commentaires publiés par item ;
8. réponses ouvertes publiées.

Filigrane en mode démo. Soumis à l'entitlement `pdf_export`.

---

## 13. Cas limites (au moins un test chacun)

| Cas | Règle |
|---|---|
| Deux appareils, mode anonyme | Un cookie par appareil. Le double vote reste possible : biais accepté et documenté. |
| Deux appareils, modes authentifiés | L'index unique `credential_uses` fait que le premier envoi l'emporte. Le second appareil affiche « Votre vote a déjà été enregistré ». |
| Lien transféré, mode anonyme ou ouvert | Autorisé. En mode ouvert, la personne doit quand même s'identifier par lien magique. |
| Lien transféré, mode fermé | Le jeton est consommé au premier vote. La régénération invalide l'ancien jeton et ne permet pas de revoter (le fingerprint ne dépend pas du jeton). |
| Brouillon puis version clôturée | Seule la réception par le serveur compte : refus, et le brouillon reste lisible localement. |
| Clôture pendant un vote | Le vote est validé avant la clôture, ou refusé. Jamais de bulletin après la clôture. |
| Import « remplacer » après un premier vote | Refusé. |
| Rotation de clé avec une version ouverte | Le démarrage échoue. |
| Sous-groupe ou complément sous k | Masqué partout, résultat vide avec motif. |
| Version entière sous k | Vues individuelles et exports 2 et 3 refusés, export 1 entièrement en `<k`. |
| Texte identifiant | Passe en `flagged`, exclu de tout jusqu'à validation. L'animateur ne peut jamais modifier un texte. |

---

## 14. Plan de livraison (environ 5 semaines)

| Lot | Contenu | Critère de fin |
|---|---|---|
| **0 — Socle** (2–3 j) | Monorepo, README, LICENSE, ADR 0001, `DECISIONS` (déjà initialisé avec les décisions de la section 16), `CHANGELOG`, `.env.example`, `.gitignore` ; Docker Compose (réplica set mono-nœud) ; CI (`backend`, `frontend`, `contract`) ; configuration avec secrets obligatoires et distincts ; **migrations de toutes les collections** (validateurs en liste blanche, dates en chaîne, UUID par motif, index et TTL) ; interfaces de repositories pour toutes les collections, implémentation pour `organizations`, `admins`, `admin_sessions` et `auth_tokens` ; `Mailer` console ; journaux filtrés ; `/health` ; **authentification animateur complète** ; module `entitlements` ; front : connexion, inscription, mot de passe oublié, tableau de bord vide, tokens de design, squelette `/v/:slug` ; seed de développement (organisation « Démo » avec `admin@demo.example.com` / `admin`, organisation « Autre » pour l'isolation) ; refus de démarrer en production si les comptes de démonstration existent | `git clone`, puis `.env`, puis `docker compose up` : l'application démarre, l'admin de démo se connecte, la CI est verte, et les tests du lot 0 (section 15) passent |
| **1 — Boucle de vote anonyme** (≈ 1 sem.) | Évaluations, versions et cycle de vie, groupes, items, import CSV, échelle et préréglages, lien et QR code, parcours de vote complet en mode anonyme, brouillon local, export 2 brut, sans interface de restitution ; premier test Playwright | 3 personnes votent sur téléphone, un envoi après clôture est refusé, et l'export ne contient ni date ni ordre |
| **2 — Moteurs, service de vote et garanties** (≈ 1 sem.) | `vote_engine` et `anonymity` complets ; **service de vote pour les trois modes**, avec la transaction `credential_uses` testée au niveau service, sans interface ; fonctions de génération des lignes des 3 exports ; détection des données identifiantes ; tous les tests de garantie de la section 15 | Tests verts en CI sur réplica set, couverture de 100 % sur `vote_engine` et `anonymity`, rapport joint |
| **3 — Accès et collecte avancée** (≈ 1 sem.) | Lien magique participant, liste blanche de domaines, jetons et QR nominatifs, régénération, participants et groupes, import CSV, questions de segmentation (4 types, tranches), questions ouvertes, console de modération, purge de rétention, rappels, convocations e-mail [S], fournisseur e-mail réel, `user/user` dans le seed | Tous les cas limites de la section 13 sont testés de bout en bout |
| **4 — Restitution pilote** (≈ 1 sem.) | Matrices, matrice agrégée, histogrammes, filtres protégés, tableau de bord de séance, sérialisation CSV des 3 exports, rapport PDF, signaux [S], glossaire [S], paramètres avancés [S], test de charge à 300 participants | Fred lit le consensus et le dissensus sans explication, et le PDF est remis tel quel à un commanditaire. Une pré-production peut être ouverte pour un pilote encadré |
| **5 — SaaS, démo et déploiement** (≈ 1 sem.) | Démo publique remise à zéro chaque nuit, ouverture de `SIGNUP_ENABLED`, compte d'essai, filigrane, fin d'essai, page super-administrateur avec TOTP, compteurs d'usage, CGU, DPA, registre, politique de confidentialité, guide animateur, déploiement sur l'hébergeur UE cible, tests de fumée en production | Un inconnu crée un essai, mène 30 votes et atteint la limite proprement ; Fred change l'offre en un clic ; les tests de fumée passent en production |

---

## 15. Tests

### Livrés dès le lot 0
- **Isolation** : test paramétré qui s'applique automatiquement à chaque nouvelle route. L'organisation A reçoit une erreur 404 sur toute ressource de B, et l'`organization_id` envoyé par le client est ignoré.
- **Architecture** (analyse statique des imports, AST) :
  - aucune importation de `pymongo` hors de `repositories/` et `db/`, et aucune importation de `motor` nulle part ;
  - aucune importation de base de données dans `vote_engine`, `anonymity` et `entitlements` ;
  - le front n'importe aucun code du back.
- **Validateurs** :
  - une insertion invalide est rejetée par MongoDB lui-même ;
  - `additionalProperties: false` est vérifié sur **chaque** collection ;
  - le domaine vote rejette les champs `credential_fingerprint`, `participant_id`, `email`, `token`, `created_at` et `updated_at` ;
  - une date du domaine vote ou identité qui n'est pas au format `YYYY-MM-DD` (par exemple un type `date`, ou une chaîne avec heure) est rejetée ;
  - un `_id` de bulletin qui n'est pas un UUID v4 est rejeté.
- **Authentification** :
  - connexion réussie et refusée, expiration de l'access token (401) ;
  - rotation du refresh token, et révocation globale en cas de réutilisation ;
  - requête sans jeton CSRF refusée ;
  - mot de passe faible refusé par l'API (alors que le seed de développement reste autorisé) ;
  - inscription refusée si `SIGNUP_ENABLED=false` ;
  - aucun jeton dans les journaux.
- **Démarrage** : échec si un secret manque, si deux secrets sont identiques, si MongoDB n'est pas en réplica set, ou en production si les comptes de démonstration existent.
- **`entitlements`** : limite atteinte, sous la limite, valeur par défaut du plan en l'absence de valeur propre.

### Livrés au lot 2 (garanties)
- **Hypothesis** (au moins 500 exemples en CI) : versions de 0 à 60 bulletins, de 1 à 3 questions fermées dont un choix multiple, réponses manquantes, groupes, filtres arbitraires, k entre 3 et 6. Propriété vérifiée sur la **sortie** de `anonymity` : aucun résultat ne porte sur moins de k bulletins, ni dans le sous-groupe ni dans son complément.
- **`anonymity`, cas explicites** :
  - segments de taille k−1, k et k+1 ; complément de taille k−1 ;
  - complément local sous filtre ;
  - choix multiple « n'a pas coché » ;
  - segment « Non renseigné » ;
  - version entière sous k ;
  - textes masqués avec leur sous-groupe ;
  - pas de sur-masquage.
- **`vote_engine`** :
  - jeux de données : vote unanime, groupe polarisé, votes partiels, filtre qui vide le groupe, un seul item ;
  - formule de score ;
  - un test par signal, y compris aux bornes 79/80 % et 49/50 % ;
  - stabilité des tris en cas d'égalité.
- **Concurrence** (MongoDB réel en réplica set) : 20 envois simultanés avec la même identité produisent exactement 1 `credential_use` et 1 bulletin, `ballot_count` incrémenté de 1, et 19 réponses « déjà enregistré ».
- **Quota** : avec `max_ballots_per_version = N`, N+5 envois concurrents produisent exactement N bulletins.
- **Clôture** : vote et clôture en parallèle, 50 répétitions, jamais de bulletin après la clôture.
- **Jeton** : régénérer le jeton après un vote ne permet pas de revoter.
- **Métadonnées** : deux bulletins créés à 61 secondes d'intervalle ont des documents identiques, en dehors de `_id`, `rand_key` et du contenu.
- **Ordre** : 100 bulletins insérés séquentiellement donnent une corrélation de rang entre `rand_key` et l'ordre d'insertion proche de 0 ; deux lectures donnent le même ordre.
- **Lignes d'export** (niveau données) :
  - aucune sortie ne combine `ballot_ref` et un segment ;
  - deux générations n'ont ni les mêmes `ballot_ref` ni le même ordre ;
  - filtre sur les exports 2 et 3 → erreur 400 ;
  - version sous k → exports refusés ;
  - textes `hidden` et `flagged` absents ;
  - item non voté → `non exprimé`.
- **Point de passage unique** : les routes de restitution et les générateurs d'export n'importent pas `repositories` ; un filtre qui isole moins de k bulletins renvoie un résultat vide avec motif.
- **Détection** : e-mail, téléphone et noms propres déclenchent `flagged`, sans faux positif sur un début de phrase.

### Lots suivants
- Cas limites de bout en bout (lot 3).
- Sérialisation CSV : BOM, `;`, neutralisation des formules (lot 4).
- PDF (lot 4).
- Playwright : créer une évaluation, voter à 3 sur viewport mobile, vérifier la matrice et les exports (lots 1 à 4).
- Charge : 300 bulletins × 30 items affichés en moins de 2 s (lot 4).
- Accessibilité : clavier, contraste AA, information jamais portée par la seule couleur (lot 4).
- Tests de fumée en production (lot 5).

---

## 16. Questions ouvertes et décisions prises

**Questions ouvertes** (à poser au début du lot concerné) :
1. Le rose (`-`) doit-il passer en orange ? (Lot 1.)
2. Quel fournisseur d'e-mail et quelle adresse d'expédition ? (Lot 3.)
3. La rétention de 12 mois convient-elle ? (Lot 3.)
4. Quel hébergeur en France ou dans l'UE, et quel nom de domaine ? (Lot 4.)
5. Quel périmètre exact pour la démo et quelles limites d'essai ? (Lot 5.)
6. Plusieurs animateurs par organisation dès le lancement ? (Lot 5.)

**Décisions prises** (à recopier dans `DECISIONS.md` au lot 0) :
- SaaS loué avec démo, prix fixés plus tard, facturation en ligne hors MVP ;
- dépôt public, monorepo, développeur seul, licence propriétaire provisoire ;
- stack React / FastAPI / MongoDB imposée, réplica set mono-nœud en développement ;
- authentification maison (JWT court et refresh token opaque, en cookies httpOnly), sans fournisseur d'identité externe ;
- 5 couleurs ;
- 3 modes de participation ;
- pas de segmentation e-mail ;
- dates en chaîne `YYYY-MM-DD` et UUID en chaîne dans le domaine vote ;
- `credential_uses` sans aucun lien vers le bulletin, fingerprint indépendant du jeton ;
- 3 exports séparés ;
- pas de modification du vote après envoi ;
- limite de débit en mémoire au MVP ;
- pilote MongoDB : `pymongo.AsyncMongoClient`, un seul client par boucle d'événements, Motor interdit ;
- versions : Python 3.13, Node 24 LTS, React 19, Vite 8 ; toutes les versions exactes épinglées et verrouillées (`uv.lock`, `package-lock.json`, images Docker à version précise).

---

## 17. Hors périmètre du MVP

- Mode QCM et cycle T0/T1 (V2).
- Nuage de mots, normalisation orthographique, mode sombre, mode présentation.
- Websockets, OAuth, SSO d'entreprise (possible plus tard derrière le même modèle de rôles), analyse sémantique.
- Mode hors-ligne : seul un brouillon local est conservé.
- Interface multilingue, paiement en ligne, modification d'un vote, lien magique animateur.
