# Lot 0 — Bloc 5 : authentification et API

## Conventions d'API
- Toutes les routes sont sous `/api`. Le front les appelle **uniquement** via `openapi-fetch` et le schéma généré.
- Format d'erreur unique : `{"error": {"code": "LIMIT_REACHED", "message": "Limite de votre offre atteinte"}}`. Codes stables en anglais, messages en français.
- `NotFound` donne toujours 404, y compris pour une ressource d'une autre organisation.
- Chaque route déclare son `response_model` et ses réponses d'erreur dans l'OpenAPI.

## Cookies
| Cookie | Contenu | Attributs |
|---|---|---|
| `abq_access` | JWT de 15 min | `HttpOnly`, `SameSite=Lax`, `Secure` selon `COOKIE_SECURE`, `Path=/api` |
| `abq_refresh` | jeton opaque de 256 bits, 14 jours | `HttpOnly`, `SameSite=Strict`, `Secure` selon `COOKIE_SECURE`, `Path=/api/auth` |
| `abq_csrf` | jeton aléatoire | **non** `HttpOnly`, `SameSite=Lax`, `Path=/` |

- **CSRF** : tout `POST`, `PUT`, `PATCH` ou `DELETE` exige l'en-tête `X-CSRF-Token` égal au cookie `abq_csrf`, comparé en temps constant. Cookie ou en-tête absent ou vide → refus. Exceptions : `login`, `signup` et `password/forgot`, protégés par `SameSite` et la limite de débit. Le jeton CSRF est renouvelé à chaque connexion et à chaque rafraîchissement.
- Rien n'est stocké dans `localStorage` ni `sessionStorage`.

## JWT (PyJWT)
- `alg` fixé à `HS256` (liste blanche ; `none` refusé).
- Contenu : `iss="abaque"`, `aud="abaque-admin"`, `sub`, `organization_id` (`null` pour le super-administrateur), `role`, `iat`, `exp`, `jti`. Tolérance de 10 s.
- Décodage avec `options={"require": ["exp","iat","sub","iss","aud","jti"]}` : un jeton sans l'une de ces revendications est refusé. `role` est validé contre l'énumération.
- Pas de liste de révocation des access tokens : après une déconnexion globale, un access token reste valide 15 min au plus. Accepté et consigné.

## Mots de passe (argon2-cffi)
- Paramètres par défaut (profil RFC 9106), avec re-hachage à la connexion si `check_needs_rehash`.
- Politique **appliquée à toutes les routes de l'API** :
  - de 12 à 128 caractères ;
  - différent de l'e-mail ;
  - absent de la liste `app/core/data/common_passwords.txt` (10 000 entrées).
- Seul le seed de développement contourne cette politique.
- **Liste de mots de passe courants** :
  - **attention à la source** : la liste « top 10 000 » de SecLists, filtrée à 12 caractères et plus, donne **bien moins** de 10 000 entrées, puisque la plupart des mots de passe courants sont courts. Partir d'une liste plus large de SecLists (par exemple le top 1 000 000, licence MIT), filtrer à 12 caractères et plus, dédoublonner en minuscules, et garder les 10 000 premiers ;
  - script `backend/scripts/build_common_passwords.py` (téléchargement, filtre, en-tête avec source et licence), exécuté une fois ; le **fichier résultant est commité**, et la CI ne télécharge rien ;
  - chargement **au démarrage** (dans le `lifespan`), et pas à la première utilisation : le démarrage échoue si le fichier est absent ou trop court ;
  - issue d'une source sous licence compatible (par exemple SecLists, licence MIT), avec la source et la licence citées en tête de fichier et dans `DECISIONS.md` ;
  - le fichier **doit exister et contenir au moins 10 000 entrées**, sinon le démarrage échoue. Une liste absente affaiblirait la politique sans que personne ne s'en aperçoive.
- `verify_password` renvoie `False` sur **toute** erreur argon2 (`VerifyMismatchError`, `VerificationError`, `InvalidHashError`).
- **Anti-énumération par le temps de réponse** : si l'e-mail est inconnu, vérifier quand même un hachage factice précalculé, pour que le temps de réponse soit le même.

## Limite de débit (en mémoire, une seule instance)
- Fenêtre glissante, avec des clés hachées : `HMAC(IP_HASH_SALT, ip)` et `HMAC(IP_HASH_SALT, email_normalisé)`.
- Connexion : 10 essais par IP et 5 par compte par tranche de 15 min, puis délai progressif.
- `signup`, `password/forgot` et `verify-email/resend` : 5 par IP et par heure.
- Au-delà : 429, message générique, en-tête `Retry-After`.
- L'IP utilisée est celle qu'uvicorn fournit après traitement des en-têtes de proxy de confiance. La limite de débit ne lit **jamais** `X-Forwarded-For` elle-même.
- Interface `RateLimiter`, pour pouvoir passer plus tard à un stockage partagé.

## Routes du lot 0
| Méthode et route | Comportement |
|---|---|
| `POST /api/auth/signup` | 403 `SIGNUP_DISABLED` si `SIGNUP_ENABLED=false`. Crée l'organisation (`plan_code="trial"`) et son owner dans une transaction, puis envoie un lien de vérification (24 h). Réponse **neutre (202)**, même si l'e-mail existe ; dans ce cas, envoi de l'e-mail « vous avez déjà un compte ». |
| `POST /api/auth/verify-email` | Consomme le jeton `verify_email`, puis `email_verified=true`. |
| `POST /api/auth/verify-email/resend` | Toujours 202. |
| `POST /api/auth/login` | Si les identifiants sont valides : 3 cookies et une `admin_session`. Sinon : `INVALID_CREDENTIALS` générique. Un compte non vérifié peut se connecter, mais `require_verified` bloque les routes métier. |
| `POST /api/auth/refresh` | Rotation atomique. Jeton **déjà consommé** : `revoke_all_for_admin`, effacement des cookies, 401 `SESSION_REVOKED`. |
| `POST /api/auth/logout` | Révoque la session et efface les cookies. |
| `POST /api/auth/password/forgot` | Toujours 202. Jeton `reset_password` de 30 min si le compte existe. |
| `POST /api/auth/password/reset` | Consomme le jeton, applique la politique, révoque **toutes** les sessions. |
| `POST /api/auth/password/change` | Authentifié, avec l'ancien mot de passe. Applique la politique et révoque les autres sessions. |
| `GET /api/auth/me` | `{id, email, role, organization: {id, name, plan_code}, email_verified}` |
| `GET /api/auth/sessions` | Sessions actives (navigateur et système abrégés, création, dernière utilisation, indicateur `current`). |
| `DELETE /api/auth/sessions/{id}` et `DELETE /api/auth/sessions` | Révoque une session ou toutes les autres. |
| `GET /api/organization` | Organisation courante et ses droits résolus. |
| `GET /health` | Voir le bloc 3. |

## Dépendances FastAPI (`app/api/deps.py`)
- `current_admin` (401 si le jeton est absent, invalide ou expiré), `require_verified`, `require_role(*roles)`.
- `current_org` (construit le `TenantContext` ; refusé pour le super-administrateur sur les routes d'organisation).
- `require_platform_admin` (routeur `/api/platform/*` vide jusqu'au lot 5).
- `csrf_protect` (appliqué via le routeur).

## `Mailer`
- Interface `send(to, template, context)`. `ConsoleMailer` journalise le destinataire **masqué** et le lien, en développement uniquement. En production, `ConsoleMailer` fait échouer le démarrage (fournisseur réel au lot 3).
- Modèles en français, en texte brut et en HTML simple : vérification, réinitialisation, compte existant.

## Tests du bloc
- `signup` : désactivé → 403 ; e-mail existant → même réponse 202 ; transaction atomique.
- `login` : succès ; échec générique identique pour un e-mail inconnu et un mauvais mot de passe ; 429 ; re-hachage.
- `refresh` : rotation ; deux appels concurrents → un seul succès ; réutilisation → révocation globale.
- Access token expiré, algorithme `none`, signature, `aud` ou `iss` invalides → 401.
- CSRF absent ou incorrect → 403.
- Réinitialisation : jeton à usage unique, jeton expiré, révocation des sessions.
- Politique : mot de passe trop court, courant ou égal à l'e-mail → 422.
- `require_verified` bloque une route métier factice.
- `GET /api/organization` avec le jeton de A ne renvoie jamais B, même avec un `organization_id` injecté.
- Après un parcours complet, aucun mot de passe, jeton, JWT ni e-mail en clair dans les journaux.
- Chaque route documente ses réponses d'erreur dans l'OpenAPI.
