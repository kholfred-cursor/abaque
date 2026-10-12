# Écriture d'un vote et `credential_uses` (lot 2, service sans interface)

## Rôle de `credential_uses`
Garantir « une identité ou un jeton vote **une seule fois** par version », **sans jamais relier** cette identité au bulletin. C'est un simple marqueur de consommation.

Document : `{ _id, organization_id, version_id, credential_fingerprint, key_id, consumed_on: "YYYY-MM-DD" }`.
- Index unique `(version_id, credential_fingerprint)`.
- `additionalProperties: false` : aucun champ du domaine vote, **ni `ballot_id` ni aucune heure**.

## Fingerprint
`HMAC-SHA256(CREDENTIAL_HMAC_KEY, "v1|" + str(version_id) + "|" + kind + ":" + valeur_normalisée)`, encodé en hexadécimal.

`compute_credential_fingerprint(settings, version_id, identity)` prend un type étiqueté, `EmailIdentity(email)` ou `ParticipantIdentity(participant_id)`, et **normalise elle-même** : un appelant ne peut pas passer une valeur non normalisée. Le préfixe `kind` (`email` ou `pid`) empêche toute collision entre un e-mail et un identifiant.

| Mode | Identité |
|---|---|
| Authentifié ouvert | `EmailIdentity`, avec l'e-mail vérifié par lien magique |
| Authentifié fermé | `EmailIdentity` si l'e-mail existe, sinon `ParticipantIdentity`. **Jamais le jeton** (régénérer le jeton permettrait alors de revoter) |
| Anonyme | `credential_uses` n'est pas utilisé |

### `normalize_email(raw)` (`app/core/identity.py`, Python pur, fonction unique pour tout le projet)
1. Normalisation Unicode NFKC.
2. Suppression des espaces **en début et en fin seulement** (y compris les espaces insécables). Un espace **interne** n'est jamais supprimé : l'adresse est rejetée par la validation. Supprimer les espaces internes transformerait silencieusement une adresse invalide en une autre adresse, valide.
3. Validation avec `email-validator` (`check_deliverability=False`), qui gère la syntaxe et l'IDNA 2008. **Ne pas utiliser le codec `idna` de Python** (IDNA 2003, incohérent avec `email-validator`).
4. Résultat : `casefold(result.local_part) + "@" + result.ascii_domain` (domaine en punycode et en minuscules, sans point final). Si la partie locale contient des caractères non ASCII, garder la partie locale normalisée par `email-validator`, puis appliquer `casefold`.
5. Les messages d'erreur **ne contiennent jamais l'adresse saisie**.

`EmailIdentity` normalise à la construction (`__post_init__`), pour qu'une identité non normalisée ne puisse pas exister.

Cette fonction est utilisée partout où un e-mail est comparé ou stocké : `participants.email`, `participant_links`, `admins.email`, la liste blanche de domaines, et le fingerprint.

**Non normalisé, risque accepté (D023, et non D014)** : pas de suppression des alias `+tag` ni des points, qui dépendent du fournisseur. En mode ouvert, une personne peut voter avec `nom+a@` puis `nom+b@`. Parades : la liste blanche de domaines, et le mode fermé quand l'unicité est critique. Le guide animateur le mentionne.

- `CREDENTIAL_HMAC_KEY` est une clé dédiée. `key_id` correspond à `credential_key_id` (voir `lot0-03-core-db.md`). **Aucune rotation tant qu'une version est `open`** : le démarrage échoue sinon.
- L'import de participants avec « remplacer l'existant » est **refusé** dès qu'une version a reçu un bulletin ; seul l'ajout reste possible.
- Le fingerprint n'est **jamais** stocké ailleurs que dans `credential_uses`, ni journalisé, ni exporté.
- La transaction utilise `session.with_transaction` de PyMongo (voir `lot0-03-core-db.md`) : **en mode anonyme, réexécuter tout le callback après un `UnknownTransactionCommitResult` créerait un bulletin en double.**

## Transaction (`run_in_transaction` basé sur `session.with_transaction`, `majority`)
1. **Verrou d'ouverture et quota en une seule écriture** :
   `versions.update_one({_id, organization_id, status:"open", ballot_count:{$lt:max}}, {$inc:{ballot_count:1}})`.
   - Si aucun document n'est modifié : on détermine la raison (version close → `VERSION_CLOSED`, quota atteint → `LIMIT_REACHED`), puis on annule.
   - Cette **écriture** crée un conflit avec une clôture concurrente, ce qu'une simple lecture ne ferait pas.
2. **Modes authentifiés** : `CredentialUseRepository.consume(...)`. En cas de clé dupliquée → `AlreadyConsumed` → 409 « Votre vote a déjà été enregistré », puis annulation.
3. `BallotWriter.write_ballot(...)` crée `ballots`, `votes`, `segment_answers` et `general_answers` :
   - UUID v4 en chaîne ;
   - `submitted_on` = jour UTC ;
   - `rand_key` aléatoire ;
   - `groups[]` en mode fermé ;
   - détection des données identifiantes sur chaque texte (`comment_status`).
4. **Modes authentifiés** : `participants.has_voted = true` ; en mode fermé, `token_hash` est invalidé.
5. Validation. La réponse ne contient **aucun** identifiant de bulletin.

**Mode anonyme** : étapes 1, 3 et 5. Un cookie aléatoire limite le double vote par navigateur. L'IP sert uniquement à la limite de débit (hachée avec `IP_HASH_SALT`, purgée à la clôture).

## Cas d'erreur
- **`UnknownTransactionCommitResult`** : on relance la validation. Si l'essai suivant rencontre la clé dupliquée, on renvoie le même message neutre « Votre vote a déjà été enregistré ».
- **Pas de clé d'idempotence fournie par le client** : ce serait un identifiant stocké avec le bulletin.
- **Participant supprimé après son vote** : son `credential_use` est conservé jusqu'à la purge de la version.
- **Purge d'une version** : les quatre collections du domaine vote, `credential_uses` et `participants` sont supprimées ensemble, et la purge est journalisée dans `version_events`.
- **Modification du vote après envoi** : hors MVP.

## Ce que `credential_uses` ne permet pas
Retrouver le bulletin de quelqu'un (ni `ballot_id` ni heure), savoir qui a voté (c'est le rôle de `participants.has_voted`), ou modifier un vote.

## Risque résiduel d'infrastructure
L'oplog et les sauvegardes de MongoDB conservent groupées les écritures d'une même transaction, donc le marqueur et le bulletin. Mesures : voir `production.md` et l'ADR 0001. La garantie contractuelle porte sur les données **applicatives**.

## Tests (lot 2)
- 20 envois concurrents avec la même identité → 1 `credential_use`, 1 bulletin, `ballot_count` + 1, 19 réponses « déjà enregistré ».
- Avec `max_ballots_per_version = N`, N+5 envois concurrents → exactement N bulletins.
- Clôture concurrente d'un vote, 50 répétitions → vote validé avant la clôture ou refusé, jamais de bulletin après.
- Régénération du jeton après un vote → impossible de revoter.
- Import « remplacer » après un bulletin → refusé.
- Rotation de clé avec une version ouverte → démarrage en échec.
- Schéma : `consumed_on` au jour près ; tout champ du domaine vote rejeté.
- Normalisation (lot 0, tests unitaires) :
  - même fingerprint pour `Jean.Dupont@Exemple.FR`, `  jean.dupont@exemple.fr `, `jean.dupont@EXEMPLE.fr.`, une forme avec espace insécable et une forme avec des caractères pleine chasse ;
  - même fingerprint pour un domaine internationalisé et sa forme punycode ;
  - `EmailIdentity` et `ParticipantIdentity` de même texte → fingerprints différents ;
  - deux versions → fingerprints différents ;
  - adresse invalide → erreur, jamais de fingerprint ;
  - `jean dupont@exemple.fr` (espace interne) → **rejetée**, et non transformée en `jeandupont@exemple.fr` ;
  - l'index unique `participants(version_id, email)` refuse le même e-mail importé sous deux formes.
