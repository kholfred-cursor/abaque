# Exports CSV et rapport PDF

Génération des lignes au lot 2 (niveau données), sérialisation CSV et PDF au lot 4.

## Règles communes
- Générés **côté serveur**, **uniquement** à travers `anonymity`.
- CSV en UTF-8 avec BOM, séparateur `;`, fin de ligne CRLF.
- **Neutralisation des formules** : toute cellule qui commence par `=`, `+`, `-`, `@` ou une tabulation est préfixée par `'`.
- Soumis à l'entitlement `csv_export` (`pdf_export` pour le PDF). Chaque génération est journalisée dans `version_events` (`export_generated`), **sans contenu**.
- Textes `hidden` et `flagged` **exclus** de tous les exports.
- Nom de fichier : `abaque_<slug>_<version>_<type>.csv`, sans date ni heure.
- **Seuil global** : si la version compte moins de k bulletins, les exports 2 et 3 sont refusés, et l'export 1 ne contient que `<k`.
- **L'export individuel avec segments est interdit pour tous les rôles**, super-administrateur compris. Aucun fichier ne combine une référence de bulletin avec un segment ou un groupe.

## Export 1 — Agrégé (le seul avec segments)
- Filtres acceptés : les mêmes que dans les vues.
- **Format large** : une ligne par **item × valeur de segment**, plus une ligne « Ensemble » par item.
  `item_position ; item_short_name ; segment_question ; segment_value ; n_expressed ; n_++ ; n_+ ; n_~ ; n_- ; n_-- ; pct_fav ; pct_mixed ; pct_defav ; score`
- Si le segment **ou son complément** (dans la population filtrée) compte moins de k bulletins : toutes les valeurs numériques valent `<k`. **La ligne reste présente**, pour que son absence ne révèle rien.
- Le seuil porte sur le nombre de bulletins du segment, pas sur l'effectif d'une couleur.
- Nombres : le libellé de la tranche.

## Export 2 — Bulletins (sans segments)
- **Toujours sur l'ensemble de la version.** Tout paramètre de filtre → 400.
- Une ligne par **bulletin × item** :
  `ballot_ref ; item_position ; item_short_name ; color_key ; color_label ; comment`
- `ballot_ref` (B001, B002…) est **attribué au hasard à chaque génération**. Il ne dérive jamais de l'UUID ni de `rand_key`.
- **L'ordre des bulletins est mélangé** à chaque génération. Les lignes d'un même bulletin restent groupées et triées par position d'item.
- Item non voté : couleur vide et mention `non exprimé`. Commentaire masqué ou à modérer : champ `comment` vide, sans mention.
- Colonnes **interdites** : segment, groupe, tranche, date, `rand_key`, UUID. Pas de questions ouvertes ni de réponses de profil libres.

## Export 3 — Textes
- **Toujours sur l'ensemble de la version.** Tout paramètre de filtre → 400.
- **Textes publiés uniquement**, sans colonne de statut :
  `type (commentaire|réponse_ouverte|réponse_profil_libre) ; item_short_name ou question ; color_label (commentaires seulement) ; text`
- Aucun `ballot_ref`, UUID, segment, groupe ni date. Lignes **entièrement mélangées** : rien ne permet de regrouper les textes d'une même personne.

## Rapport PDF (WeasyPrint)
- Construit à partir de données **déjà passées par `anonymity`**, dans `run_in_executor`, sans aucun accès à la base depuis le thread.
- Ordre :
  1. titre ;
  2. chiffres clés ;
  3. répartition globale ;
  4. matrice des items ;
  5. histogrammes par item ;
  6. répartition par segment (`<k` appliqué) ;
  7. commentaires publiés par item ;
  8. réponses ouvertes publiées.
- Couleurs et symboles lus dans `docs/design/scale.json`. Filigrane « Démo » pour les offres `trial` et `demo`.

## Tests
- Aucune sortie ne combine `ballot_ref` et un segment.
- Deux générations n'ont ni les mêmes `ballot_ref` ni le même ordre.
- Filtre sur les exports 2 et 3 → 400 ; version sous k → exports 2 et 3 refusés et export 1 entièrement en `<k`.
- Segment ou complément de taille k−1 → `<k` ; complément local sous filtre de groupe ; choix multiple « n'a pas coché » ; dans un segment de taille k, une couleur à 1 vote reste visible.
- Textes `hidden` et `flagged` absents ; item non voté → `non exprimé` ; une cellule commençant par `=` est neutralisée.
