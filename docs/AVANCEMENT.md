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
Vérifié : connexion du compte de démonstration dans un vrai navigateur ; CI verte sur la pull request #11, fusionnée dans `main` le 13 octobre 2026. **Lot 0 terminé.**

## Lots suivants

| Lot | Contenu | État |
|---|---|---|
| 1 | Boucle de vote anonyme (évaluations, versions, items, lien et QR code, parcours de vote mobile) | en cours : 1a ✅ API des évaluations, 1b ✅ vote anonyme et export, 1c ✅ écrans de l'animateur, 1d ✅ vote sur téléphone ; reste 1e (test de bout en bout en CI) |
| 2 | Moteurs, service de vote pour les 3 modes, garanties d'anonymat | à faire |
| 3 | Accès nominatifs et collecte avancée (liens magiques, segmentation, questions ouvertes, e-mails réels) | à faire |
| 4 | Restitution (matrices, histogrammes, exports CSV et PDF) | à faire |
| 5 | SaaS, démo publique, essai, super-administrateur, documents légaux, déploiement | à faire |

## Ce que l'application sait faire aujourd'hui

### À l'écran
- Créer une évaluation, rédiger ses items par groupes (ou importer un fichier CSV), les réordonner à la souris ou au clavier, choisir l'échelle et les textes d'accueil et de fin.
- Ouvrir le vote, afficher le lien et le QR code à projeter ou à télécharger, suivre le nombre de réponses, clore, rouvrir, archiver ou dupliquer une version, exporter les réponses.
- Supprimer une évaluation après confirmation.
- Voter sur téléphone avec le lien ou le QR code : accueil, une partie à la fois, 5 grandes zones de couleur, commentaire facultatif, progression visible, vérification puis envoi définitif. Un rechargement ne fait pas perdre les réponses en cours ; un envoi après la clôture est refusé et les réponses restent affichées.
- Se connecter, s'inscrire, confirmer son e-mail (avec renvoi du lien depuis une bannière), demander puis choisir un nouveau mot de passe ; afficher le mot de passe pendant la saisie.
- Voir un tableau de bord vide (« Vous n'avez pas encore d'évaluation ») avec le nom de l'organisation et l'offre.
- Voir ses sessions ouvertes, en fermer une ou toutes les autres.
- Rester connecté après un rechargement ; être renvoyé à la connexion, avec un message, quand la session a expiré, puis revenir à la page demandée.
- Utiliser toutes les pages au clavier et sur un téléphone de 360 px de large, avec un contraste suffisant et des messages d'erreur en français.
- Ouvrir un lien participant `/v/…`, qui affiche pour l'instant « Bientôt disponible ».

### Côté serveur (lot 1)
- Créer une évaluation (avec un lien public aléatoire qui ne révèle ni l'organisation ni le titre), la modifier, la dupliquer, la supprimer avec tout son contenu.
- Rédiger les items par groupes, les réordonner, les importer ou les exporter en CSV (le fichier d'exemple `docs/samples/items.csv` s'importe tel quel).
- Choisir l'échelle : « Accord », « Score 1–5 » ou libellés personnalisés.
- Ouvrir, clore, rouvrir et archiver une version ; une seule version ouverte à la fois ; chaque étape est journalisée. Les items sont figés dès la première réponse : on duplique la version pour les changer.
- Respecter le nombre d'évaluations actives permis par l'offre, même avec des créations simultanées.
- Recevoir les votes anonymes par le lien public : aucun bulletin ne contient d'heure ni d'identité, un même navigateur ne vote qu'une fois, un vote envoyé après la clôture est refusé (« Cette consultation est close, votre réponse n'a pas été enregistrée »), et le nombre de réponses permis par l'offre est respecté même avec des envois simultanés.
- Mettre de côté les commentaires qui semblent contenir une adresse e-mail, un numéro de téléphone ou un nom propre : ils n'apparaissent nulle part tant qu'ils ne sont pas validés.
- Exporter les bulletins en CSV à partir de 3 réponses : références et ordre tirés au hasard à chaque export, aucune date.

### Côté serveur (lot 0)

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
- **D036 à D038** — lien public aléatoire ; une seule version ouverte par évaluation ; contenu enregistré d'un bloc avec numéro de révision.
- **D033** — comptes de démonstration en `demo.example.com` (les adresses `.local` ne pouvaient pas se connecter).
- **D034** — front : aucun attribut `style` (CSP), police auto-hébergée, état de connexion lu uniquement depuis l'API, renouvellement de session unique et partagé.
- **D032** — tests rangés par domaine ; isolation testée automatiquement sur chaque route d'organisation.
- **D031** — inscription et mot de passe oublié toujours neutres (202) ; un mot de passe refusé ne fait pas perdre le lien de réinitialisation.

## Risques acceptés (lot 0)

- Deux créations simultanées d'animateurs peuvent dépasser le quota de 1.
- Deux demandes simultanées peuvent laisser deux jetons de réinitialisation actifs (chacun à usage unique, avec expiration).
- Après une déconnexion, un access token déjà émis reste valide au plus 15 minutes.
- Limite de débit en mémoire : valable tant que l'API tourne en un seul processus (D013).
