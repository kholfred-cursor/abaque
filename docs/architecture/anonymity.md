# Module `anonymity` et règles k

## Rôle
`app/anonymity` (Python pur) est l'**unique point de passage** entre les bulletins filtrés et toute sortie : API de restitution, console de commentaires, PDF et CSV. Les routes de restitution et les générateurs d'export n'importent jamais `repositories` directement ; seuls `anonymity`, `services/restitution` et `services/export` peuvent lire via `BallotReader`.

## Garantie contractuelle (texte imposé)
> **Garantie technique** : aucune donnée applicative ne relie directement un bulletin à l'identité d'un participant. Il n'existe ni clé, ni référence, ni identifiant, ni empreinte commune entre le domaine identité et le domaine vote, et aucune vue, aucun export ni aucune API ne permet une telle jointure.
> **Protections contre la réidentification statistique** : seuil k sur les sous-groupes et leurs compléments, minimisation des métadonnées, exports individuels sans segments. Ces mesures réduisent fortement le risque de recoupement contextuel sans pouvoir l'exclure totalement.

Il est interdit d'écrire « anonymat total » ou « impossible à relier ».

## Règles
- **Seuil k** : 3 par défaut, modifiable **à la hausse uniquement**, appliqué à tous les rôles, super-administrateur compris.
- **Seuil global** : si la version compte moins de k bulletins, les vues individuelles (matrices brute, participants et mixte) et les exports 2 et 3 sont **refusés**, et l'export 1 ne contient que `<k`.
- **Sous-groupe et complément** : une sélection est masquée si le sous-groupe **ou son complément** compte moins de k bulletins.
  - Le complément se calcule **dans la population filtrée**. Avec un filtre « Groupe = Site A », le complément de « Fonction = Manager » est « Site A et non Manager ».
  - **Choix multiple** : segment « a coché X », complément « n'a pas coché X » (y compris sans réponse).
  - **Absence de réponse** : segment « Non renseigné », soumis à la même règle.
- **Masquage** : l'élément reste visible, grisé, avec la mention « effectif insuffisant ». L'API renvoie un résultat vide avec un **motif**, jamais les données. Les textes d'un sous-groupe masqué sont masqués avec lui dans les vues filtrées et dans le PDF.
- **Pas de sur-masquage** : dans un segment d'au moins k bulletins, une couleur votée par une seule personne reste affichée.

## Risque résiduel d'homogénéité (documenté, non corrigé au MVP)
Si tous les bulletins d'un segment d'au moins k personnes portent la même couleur, savoir qu'une personne appartient à ce segment révèle son vote. C'est inhérent à toute restitution par groupe. Il est mentionné dans l'ADR, le DPA et le guide animateur, avec ce conseil : éviter les segments très petits ou homogènes.

## Minimisation des métadonnées
- Dates au jour près (`YYYY-MM-DD`) dans `ballots` et `credential_uses` ; aucune date de vote dans `participants`.
- UUID v4 dans le domaine vote (pas d'ObjectId, qui contient l'heure de création).
- Ordre aléatoire stable (`rand_key`) partout ; jamais l'ordre d'insertion.
- Aucun identifiant de participant, jeton ou fingerprint dans les journaux des routes de vote.
- Tableau de bord de séance : compteurs uniquement.

## Segmentation
- Seules les questions **fermées** (choix unique, choix multiple) et les **tranches** des questions numériques servent de segments et de filtres.
- **Aucun type e-mail.** Le texte libre n'est jamais un segment : il est stocké dans `general_answers`.
- `ballots.groups[]` (mode fermé) n'est lu qu'à travers `anonymity`.

## Détection des données identifiantes
- À la réception de chaque texte (commentaire, réponse ouverte, réponse de profil libre) : motifs e-mail, téléphone français ou international, et deux mots consécutifs à majuscule initiale hors début de phrase.
- Un texte repéré passe en `flagged` : il est exclu des vues, du PDF et des exports tant que l'animateur ne l'a pas publié. L'animateur peut le publier ou le masquer, **jamais le modifier**.

## Tests (lot 2)
Voir `tests-garanties-lot2.md`.
