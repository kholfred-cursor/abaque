# Lot 0 — Bloc 7 : frontend

## Structure
```
frontend/src/
├── main.tsx   App.tsx   router.tsx
├── shared/
│   ├── api/      schema.d.ts (généré, COMMITÉ), client.ts, errors.ts
│   ├── auth/     AuthProvider.tsx, useAuth.ts, RequireAuth.tsx
│   ├── design/   tokens.ts, tokens.css, scale.ts
│   ├── ui/       Button, Input, Field, Alert, Banner, Spinner, Layout
│   ├── i18n/     fr.ts (tous les textes)
│   └── hooks/
├── admin/        LoginPage, SignupPage, VerifyEmailPage, ForgotPasswordPage,
│                 ResetPasswordPage, DashboardPage, SessionsPage
├── vote/         VotePlaceholderPage (/v/:slug)
├── restitution/  (vide)
└── platform/     (vide)
```

## Choix techniques
- React 19, React Router 7 en **mode bibliothèque** (`createBrowserRouter`, dépendance `react-router` seule, sans `@react-router/dev`).
- TypeScript strict, avec `noUncheckedIndexedAccess` et `exactOptionalPropertyTypes`.
- Vite 8, Node 24.
- **Pas de bibliothèque de composants**, ni de CSS-in-JS qui injecte des `<style>` (CSP `style-src 'self'`). CSS Modules et variables CSS issues des tokens.
- **Polices auto-hébergées** dans `public/fonts` : aucun CDN ni Google Fonts.
- **Aucune donnée d'authentification dans `localStorage` ou `sessionStorage`.** L'état vient de `GET /api/auth/me`.
- Pas de `dangerouslySetInnerHTML`.

## Client API (`shared/api/client.ts`)
- `createClient<paths>({ baseUrl: "/api", credentials: "include" })` (`openapi-fetch`).
- **Middleware CSRF** : `X-CSRF-Token` lu dans le cookie `abq_csrf`, ajouté sur `POST`, `PUT`, `PATCH` et `DELETE`.
- **Middleware de rafraîchissement** :
  - sur une erreur 401 (hors `/auth/login`, `/auth/refresh` et `/auth/signup`), un seul `POST /auth/refresh`, avec une promesse partagée entre les requêtes simultanées ;
  - en cas de succès, la requête initiale est rejouée **une seule fois** ;
  - en cas d'échec ou de `SESSION_REVOKED`, l'état est vidé et l'utilisateur redirigé vers `/connexion?expired=1`.
- `errors.ts` : `{"error":{code,message}}` devient `ApiError` ; les codes connus correspondent à des messages de `fr.ts`, les autres à un message générique.

## Authentification
- `AuthProvider` (`loading`, `authenticated` ou `anonymous`) expose `login`, `logout` et `refreshMe`.
- `RequireAuth` redirige vers `/connexion` en conservant la page demandée.
- Bandeau « Vérifiez votre adresse e-mail » avec un bouton de renvoi si `email_verified=false`.

## Routes
| Chemin | Page |
|---|---|
| `/connexion` | Connexion |
| `/inscription` | Inscription (`SIGNUP_DISABLED` → « Inscriptions fermées ») |
| `/verifier-email?token=` | Vérification de l'e-mail |
| `/mot-de-passe-oublie` | Demande de réinitialisation |
| `/reinitialiser?token=` | Nouveau mot de passe |
| `/` | « Mes évaluations », vide, protégée |
| `/compte/sessions` | Sessions actives, protégée |
| `/v/:slug` | Page participant « Bientôt disponible » : **publique**, mise en page mobile-first distincte, sans dépendance à l'authentification animateur |
| `*` | 404 |

Les jetons présents dans l'URL sont envoyés à l'API puis **retirés** avec `history.replaceState`.

## Formulaires
- Libellés explicites, erreurs reliées au champ (`aria-describedby`), focus sur le premier champ en erreur.
- Mot de passe : règle affichée, bouton « afficher », `autocomplete` correct.
- Bouton désactivé pendant l'envoi, sans double soumission.
- Réponses neutres de l'API : « Si un compte correspond, un e-mail a été envoyé. »

## Tokens de design
- `tokens.ts` est la source unique ; `tokens.css` en est le miroir, vérifié par un test d'égalité.
- `scale.ts` décrit l'échelle à 5 couleurs dans l'ordre : `{ key, hex, textColor, symbol, labelKey, weight }`.
  - Valeurs : `#2e8b3c`, `#7ecb4d`, `#f5d94e`, `#f0a8b8`, `#e83030`.
  - Symboles distincts : `++`, `+`, `~`, `−`, `−−`.
  - `textColor` donne un contraste d'au moins 4,5:1.
- Copie JSON dans `docs/design/scale.json` (utilisée par le PDF au lot 4), avec un test d'égalité.
- Page `/dev/tokens`, en développement uniquement.

## Accessibilité et responsive
- Utilisable sans zoom à 360 px, zones tactiles d'au moins 44 px, navigation au clavier, focus visible.
- `lang="fr"` et un titre par page.
- Aucune information portée par la seule couleur.

## Outils
- ESLint (TypeScript, `react-hooks`, `jsx-a11y`) et Prettier.
- Scripts : `dev`, `build`, `preview`, `lint`, `typecheck`, `test`, `gen:api` (`openapi-typescript ../openapi.json -o src/shared/api/schema.d.ts`).
- Tests : Vitest, Testing Library, MSW.

## Tests du lot 0
- **Client API** :
  - en-tête CSRF sur les requêtes modifiantes, absent sur `GET` ;
  - une erreur 401 sur trois requêtes simultanées déclenche **un seul** rafraîchissement, puis les rejoue ;
  - un rafraîchissement en échec redirige ;
  - `SESSION_REVOKED` vide l'état.
- **Authentification** : `RequireAuth` redirige ; bandeau de vérification affiché.
- **Pages** :
  - erreur générique à la connexion ;
  - redirection vers la page demandée ;
  - `SIGNUP_DISABLED` ;
  - message neutre de mot de passe oublié ;
  - jeton retiré de l'URL.
- **Tokens** : contraste d'au moins 4,5:1, symboles distincts, égalité `tokens.ts` / `tokens.css`, égalité `scale.ts` / `scale.json`.
- **Statiques** : aucun `localStorage` ni `sessionStorage` dans `src/` ; aucun import de `backend`.

## Critère de fin
Sur `http://localhost:5173` : connexion avec `admin@abaque.local` / `admin`, tableau de bord vide, page des sessions, déconnexion. `/v/test` affiche « Bientôt disponible » sur mobile. `lint`, `typecheck`, `test` et `build` passent, et le job `contract` est vert.
