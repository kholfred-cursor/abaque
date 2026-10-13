#!/usr/bin/env bash
# Initialise le réplica set rs0 de façon idempotente.
set -euo pipefail

HOST="mongo:27017"
MAX_WAIT=30

echo "[mongo-init] Vérification du réplica set..."

mongosh --host "$HOST" --quiet --eval '
  try {
    rs.status();
    print("[mongo-init] Réplica set déjà initialisé.");
  } catch (e) {
    if (e.codeName === "NotYetInitialized") {
      rs.initiate({ _id: "rs0", members: [{ _id: 0, host: "mongo:27017" }] });
      print("[mongo-init] Réplica set rs0 initialisé.");
    } else {
      print("[mongo-init] Erreur inattendue : " + e);
      quit(1);
    }
  }
'

echo "[mongo-init] Attente du primaire..."
elapsed=0
while [ "$elapsed" -lt "$MAX_WAIT" ]; do
  if mongosh --host "$HOST" --quiet --eval "db.hello().isWritablePrimary" 2>/dev/null | grep -q "true"; then
    echo "[mongo-init] Primaire prêt."
    exit 0
  fi
  sleep 1
  elapsed=$((elapsed + 1))
done

echo "[mongo-init] ERREUR : primaire non disponible après ${MAX_WAIT}s" >&2
exit 1
