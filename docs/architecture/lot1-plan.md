# Lot 1 — Boucle de vote anonyme : découpage et choix

Référence : `docs/PROMPT_MVP.md`, sections 9.1, 9.2, 9.4, 12 (export 2) et 14.

**Critère de fin du lot** : 3 personnes votent sur téléphone, un envoi après clôture est refusé, et l'export ne contient ni date ni ordre.

**Hors lot 1** (ne pas commencer) : modes authentifiés, participants, questions de segmentation et questions ouvertes (lot 3) ; `vote_engine`, `anonymity` complet, exports 1 et 3 (lots 2 et 4) ; restitution (lot 4).

## Blocs

| Bloc | Contenu | Vérification |
|---|---|---|
| 1a | API animateur : évaluations (créer, lire, modifier, dupliquer, supprimer), versions et cycle de vie journalisé, groupes et items (contenu remplacé d'un bloc), échelle et préréglages, import et export CSV des items, quota `max_active_evaluations` | tests HTTP, isolation automatique de chaque nouvelle route, types OpenAPI régénérés |
| 1b | API publique de vote : lecture d'une version ouverte par son lien, envoi d'un bulletin anonyme (transaction étapes 1, 3 et 5), cookie anti double vote, limite de débit par IP hachée, détection des textes identifiants, seuil k global, export 2 en CSV | tests HTTP et MongoDB réel : clôture concurrente, quota concurrent, métadonnées identiques, export sans date ni ordre |
| 1c | Écrans animateur : liste des évaluations, éditeur (évaluation, items avec glisser-déposer, import CSV, échelle), versions (ouvrir, clore, rouvrir, archiver, dupliquer), lien et QR code, téléchargement de l'export | tests de composants |
| 1d | Parcours de vote mobile : introduction, vote par groupe, progression, brouillon local, envoi avec récapitulatif, écran de fin, consultation close | tests de composants, 360 px |
| 1e | Premier test Playwright (créer, voter à 3 sur mobile, clore, envoi refusé, export), job CI `e2e`, Dependabot limité aux mises à jour mineures | CI verte |

## Choix (détail dans `docs/DECISIONS.md`)

- **D035** — Le rose est conservé pour `-` (question ouverte n° 1 close).
- **D036** — Lien public : `slug` aléatoire de 10 caractères, unique sur toute la plateforme (nouvel index `uq_evaluations_slug`). Il ne révèle ni l'organisation ni le titre.
- **D037** — Une seule version ouverte par évaluation ; `/v/:slug` sert cette version. Transitions : `draft → open`, `open → closed`, `closed → open`, `draft | closed → archived`. Le contenu (groupes, items, libellés) est modifiable tant que la version n'a reçu aucun bulletin et n'est pas archivée.
- **D038** — Le contenu d'une version est enregistré d'un bloc (`PUT /api/versions/{id}/content`) : le glisser-déposer, l'ajout et la suppression se font dans l'éditeur, puis un seul enregistrement valide l'ensemble dans une transaction.
- **D039** — Brouillon local du votant : seule exception à l'interdiction du stockage navigateur, limitée à `frontend/src/vote/draft.ts`, une clé par version, effacée après l'envoi.
- **D040** — Vote anonyme au lot 1 : service de vote limité au mode anonyme, que le lot 2 généralisera aux trois modes. Le cookie anti double vote est aléatoire, `httpOnly`, propre à la version et limité au chemin de l'évaluation ; il ne contient aucune donnée.
- **D041** — Détection des textes identifiants et seuil k global livrés dès le lot 1 dans `app/anonymity`, car l'export 2 et les commentaires en ont besoin. Le lot 2 complète `anonymity` (sous-groupes, compléments).
- **D042** — Évaluations « actives » pour le quota : celles qui ont au moins une version non archivée.
- **D043** — Au lot 1, seul le mode `anonymous` peut être choisi ; les autres modes sont refusés (400) jusqu'au lot 3.

## Réalisation

- **1a** (2026-10-13) : routes `/api/evaluations` et `/api/versions/{id}` (contenu, transitions, duplication, CSV des items). Service `app/services/content.py`, repository `app/repositories/mongo/content.py`.
- **1b** (2026-10-14) : routes `/api/public/v/{slug}` (lecture, envoi) et `/api/versions/{id}/exports/ballots.csv`. Écriture des bulletins dans `app/repositories/mongo/vote.py` (seul chemin d'écriture), lecture pour l'export par `MongoBallotReader` dans le paquet `app/services/export/` (seul paquet autorisé avec la restitution, test d'architecture). Les routes publiques sont exemptées du jeton CSRF (aucune session) mais exigent un corps JSON et refusent une origine étrangère. La course « clôture pendant un vote » est testée sur la cohérence des compteurs ; un bulletin ne portant aucune heure, l'instant de son écriture n'est pas observable par conception.
