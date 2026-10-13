# Avancement d'Abaque

Mis à jour à chaque bloc intégré. Branche de travail : `lot-0-socle` ; `main` ne reçoit que du code testé.

## Lot 0 — Socle

| Bloc | Contenu | État |
|---|---|---|
| 1 | Racine, documentation, licence, ADR, décisions, journal des modifications | ✅ |
| 2 | Docker Compose (MongoDB en réplica set), Dockerfiles, nginx, CI, Dependabot | ✅ |
| 3 | Configuration, sécurité, journaux masqués, client MongoDB, 21 schémas, index, migrations, seed, `/health` | ✅ |
| 3c | Squelette du front (Vite, lint, types générés depuis l'API, 3 routes) | ✅ |
| 4a | Droits par offre, domaine, repositories organisations et animateurs | ✅ |
| 4b | Sessions, jetons à usage unique, tests de concurrence et d'architecture | ✅ |
| 5a | Connexion, renouvellement de session, déconnexion, profil, organisation, CSRF, limite de débit | ✅ |
| 5b | Inscription, vérification de l'e-mail, mot de passe oublié / réinitialisation / changement, gestion des sessions | ✅ |
| 6 | Tests d'isolation appliqués automatiquement à toutes les routes, transactions sous panne, validateurs en profondeur | ✅ |
| 7 | Écrans React (connexion, inscription, mot de passe, tableau de bord, sessions, tokens de design, `/v/:slug`) | ✅ |

**Fin du lot 0** : `git clone`, `.env`, `docker compose up` ; l'administrateur de démonstration se connecte ; la CI est verte.
Les deux premiers points sont vérifiés dans un vrai navigateur avec `admin@demo.example.com` / `admin`. La CI sera vérifiée sur la pull request `lot-0-socle` → `main`.

## Lots suivants

| Lot | Contenu | État |
|---|---|---|
| 1 | Boucle de vote anonyme (évaluations, versions, items, lien et QR code, parcours de vote mobile) | à faire |
| 2 | Moteurs, service de vote pour les 3 modes, garanties d'anonymat | à faire |
| 3 | Accès nominatifs et collecte avancée (liens magiques, segmentation, questions ouvertes, e-mails réels) | à faire |
| 4 | Restitution (matrices, histogrammes, exports CSV et PDF) | à faire |
| 5 | SaaS, démo publique, essai, super-administrateur, documents légaux, déploiement | à faire |

## Ce que l'application sait faire aujourd'hui

### À l'écran
- Se connecter, s'inscrire, confirmer son e-mail (avec renvoi du lien depuis une bannière), demander puis choisir un nouveau mot de passe ; afficher le mot de passe pendant la saisie.
- Voir un tableau de bord vide (« Vous n'avez pas encore d'évaluation ») avec le nom de l'organisation et l'offre.
- Voir ses sessions ouvertes, en fermer une ou toutes les autres.
- Rester connecté après un rechargement ; être renvoyé à la connexion, avec un message, quand la session a expiré, puis revenir à la page demandée.
- Utiliser toutes les pages au clavier et sur un téléphone de 360 px de large, avec un contraste suffisant et des messages d'erreur en français.
- Ouvrir un lien participant `/v/…`, qui affiche pour l'instant « Bientôt disponible ».

### Côté serveur

- Démarrer en vérifiant sa configuration : secrets présents, différents et assez longs ; règles propres à la production (cookies sécurisés, pas de comptes de démonstration, pas d'envoi d'e-mails factice).
- Créer et faire évoluer la base de données à chaque démarrage, sans rien supprimer, avec des validateurs qui refusent tout champ non prévu — en particulier tout champ identifiant dans les données de vote.
- Créer une organisation et son propriétaire en une seule opération indivisible ; appliquer les droits de l'offre (nombre d'évaluations, de bulletins, d'animateurs, fonctionnalités) avec des surcharges propres à chaque organisation.
- Garantir qu'un animateur ne voit jamais les données d'une autre organisation (réponse 404, jamais 403).
- Connecter un animateur avec 3 cookies (session courte, renouvellement, protection CSRF) ; refuser de la même façon un e-mail inconnu et un mauvais mot de passe ; bloquer les tentatives répétées.
- Renouveler la session sans déconnecter l'utilisateur qui a deux onglets ouverts ; détecter le rejeu d'un jeton volé et fermer alors toutes ses sessions.
- Inscrire une nouvelle organisation en essai, sans jamais révéler si une adresse a déjà un compte ; envoyer et vérifier le lien de confirmation de l'e-mail.
- Réinitialiser un mot de passe oublié par un lien valable 30 minutes et utilisable une seule fois, puis fermer toutes les sessions ; changer son mot de passe en gardant la session en cours.
- Lister ses sessions actives (« Firefox · Windows », date de création, session courante) et en fermer une ou toutes les autres.
- Refuser automatiquement, dès la CI, toute nouvelle route d'organisation qui n'aurait pas son test d'isolation.
- Résister aux pannes MongoDB pendant une transaction sans jamais écrire deux fois la même donnée (garantie requise pour le vote au lot 2).
- Ne jamais écrire de mot de passe, de jeton ni d'adresse e-mail en clair dans les journaux.

## Décisions récentes

- **D020** — dépassement d'offre : réponse 403 `LIMIT_REACHED`.
- **D028** — les droits stockés sont des surcharges de l'offre, recalculés à chaque lecture : changer d'offre s'applique immédiatement.
- **D029** — fenêtre de 10 s pour le renouvellement de session simultané de deux onglets ; au-delà, rejeu = révocation de toutes les sessions.
- **D030** — l'API et les services passent par `MongoStore` et n'importent jamais `pymongo`.
- **D033** — comptes de démonstration en `demo.example.com` (les adresses `.local` ne pouvaient pas se connecter).
- **D034** — front : aucun attribut `style` (CSP), police auto-hébergée, état de connexion lu uniquement depuis l'API, renouvellement de session unique et partagé.
- **D032** — tests rangés par domaine ; isolation testée automatiquement sur chaque route d'organisation.
- **D031** — inscription et mot de passe oublié toujours neutres (202) ; un mot de passe refusé ne fait pas perdre le lien de réinitialisation.

## Risques acceptés (lot 0)

- Deux créations simultanées d'animateurs peuvent dépasser le quota de 1.
- Deux demandes simultanées peuvent laisser deux jetons de réinitialisation actifs (chacun à usage unique, avec expiration).
- Après une déconnexion, un access token déjà émis reste valide au plus 15 minutes.
- Limite de débit en mémoire : valable tant que l'API tourne en un seul processus (D013).
