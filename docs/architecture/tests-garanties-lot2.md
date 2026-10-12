# Tests de garantie — lot 2

Le **service de vote complet** (trois modes, transaction `credential_uses`) est construit et testé au lot 2, **au niveau service, sans interface**. Les parcours d'authentification des participants arrivent au lot 3.

Critère de fin : tests verts en CI sur MongoDB en réplica set, **couverture de 100 % (branches) sur `vote_engine` et `anonymity`**, rapport joint à la livraison.

## Propriétés (Hypothesis, au moins 500 exemples en CI)
- Données générées : versions de 0 à 60 bulletins, de 1 à 3 questions fermées dont au moins un choix multiple, réponses manquantes, groupes, combinaisons de filtres arbitraires, k entre 3 et 6.
- Propriété vérifiée sur la **sortie** de `anonymity`, pour toutes les vues et lignes d'export : aucun résultat ne porte sur moins de k bulletins, ni dans le sous-groupe ni dans son complément.

## `anonymity` : cas explicites
- Segments de taille k−1, k et k+1 ; complément de taille k−1.
- Complément local sous un filtre de groupe.
- Choix multiple « n'a pas coché X » sous k.
- Segment « Non renseigné ».
- Version entière sous k.
- Textes masqués avec leur sous-groupe.
- Pas de sur-masquage : dans un segment de taille k, une couleur à 1 vote reste visible.

## `vote_engine`
- Jeux de données : vote unanime, groupe polarisé, votes partiels, filtre qui vide le groupe, un seul item.
- Formule de score : `2·(++) + (+) − (−) − 2·(−−)` ; pourcentages calculés sur les votes exprimés.
- Un test par signal, aux bornes : consensus à 79/80 %, item incertain à 49/50 %, voix minoritaire.
- Stabilité des tris en cas d'égalité :
  - items : score, puis `++`, puis position ;
  - bulletins : `ballotScore`, puis nombre de votes exprimés, puis `rand_key`.

## Concurrence et clôture (MongoDB réel)
- 20 envois simultanés avec la même identité → 1 `credential_use`, 1 bulletin, `ballot_count` + 1, 19 réponses « déjà enregistré ».
- Quota : avec `max_ballots_per_version = N`, N+5 envois concurrents → N bulletins exactement.
- Vote et clôture en parallèle, 50 répétitions → jamais de bulletin après la clôture.
- Régénération du jeton après un vote → impossible de revoter.

## Métadonnées et ordre
- Deux bulletins créés à 61 secondes d'intervalle ont des documents identiques, en dehors de `_id`, `rand_key` et du contenu des votes.
- Aucune date n'a de précision plus fine que le jour.
- 100 bulletins insérés séquentiellement : corrélation de rang entre `rand_key` et l'ordre d'insertion proche de 0 ; deux lectures donnent le même ordre.

## Lignes d'export (niveau données)
Voir `exports.md`, section Tests.

## Point de passage unique
- Test d'architecture : les routes de restitution et les générateurs d'export n'importent pas `repositories`, et `BallotReader` n'est importé que par les modules autorisés.
- Test fonctionnel : un filtre qui isole moins de k bulletins renvoie un résultat vide avec un motif.

## Détection des données identifiantes
E-mail, téléphone et noms propres déclenchent `flagged`, sans faux positif sur un mot en début de phrase.
