# Exploitation et production

## Processus
- **Un seul worker uvicorn** (D013). La limite de débit est en mémoire et APScheduler tourne dans le processus de l'API ; plusieurs workers dupliqueraient les tâches planifiées et affaibliraient la limite de débit.
- **Garde-fou** : en production, l'application refuse de démarrer si `WEB_CONCURRENCY > 1` avec `RATE_LIMIT_BACKEND=memory`.
- **Conditions pour passer à plusieurs workers** :
  1. limite de débit sur un stockage partagé (MongoDB avec TTL ou Redis) ;
  2. scheduler sorti de l'API (service `worker` dédié ou verrou en base) ;
  3. tâches planifiées **idempotentes**. Cette condition est exigée **dès maintenant** : purges, rappels, remise à zéro de la démo et fin d'essai ne doivent rien dupliquer si elles sont relancées.
- La génération de PDF tourne dans `run_in_executor` pour ne pas bloquer la boucle. Un test de charge à 300 participants est prévu au lot 4.

## Proxy et en-têtes
- nginx sert le front et proxifie `/api/` et `/health` vers l'API (`proxy_pass http://api:8000;`, **sans barre finale**). Voir `lot0-02-docker-ci.md`.
- uvicorn : `--proxy-headers --forwarded-allow-ips=<réseau interne du proxy>`, **jamais `*`**, sinon l'IP peut être usurpée et la limite de débit contournée.
- En-têtes de sécurité dans chaque `location`, CSP stricte, et HSTS seulement derrière TLS.
- TLS terminé avant ou dans nginx. `COOKIE_SECURE=true` est obligatoire.

## MongoDB
- Réplica set à 3 nœuds, ou Atlas en région UE. MongoDB 7.0 (D006 : fin de support à vérifier et suivre).
- Profiler désactivé, `slowms` élevé, aucune journalisation applicative des requêtes complètes sur les routes de vote.
- **Oplog** : taille minimale compatible avec le réplica set.
- **Sauvegardes** : chiffrées, rétention courte et documentée, accès réservé à l'exploitation, jamais au rôle applicatif.
- Ces deux points sont mentionnés dans le DPA et le registre des traitements.
- Utilisateur MongoDB applicatif avec des droits limités à la base `abaque`, sans accès administrateur.

## Rétention
- Purge automatique d'une version selon `retention_months` (12 mois par défaut, à confirmer), rappel à l'animateur 30 jours avant avec un lien d'export, purge journalisée.
- IP hachées purgées à la clôture.
- Organisations d'essai : lecture seule pendant 30 jours après la fin de l'essai, puis purge.

## Secrets
- `JWT_SECRET`, `CREDENTIAL_HMAC_KEY` et `IP_HASH_SALT` : distincts, générés avec `openssl rand -hex 32`, stockés dans le gestionnaire de secrets de l'hébergeur, jamais dans le dépôt.
- **Aucune rotation de `CREDENTIAL_HMAC_KEY` tant qu'une version est ouverte.**

## Hébergement
- Données dans l'UE, de préférence en France. Hébergeur, nom de domaine et fournisseur d'e-mail à décider (questions ouvertes de `PROMPT_MVP.md`).
- Une pré-production est possible après le lot 4 pour un pilote encadré. La production publique arrive avec le lot 5, accompagnée de tests de fumée.
