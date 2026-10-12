#!/usr/bin/env bash
# Vérifie les en-têtes de sécurité et le proxy de l'image de production.
# Usage : scripts/check-headers.sh http://localhost:8080
set -euo pipefail

BASE="${1:-http://localhost:8080}"
FAIL=0

check_headers() {
  local url="$1"
  local headers
  headers="$(curl -sI "$url")"
  for h in "Content-Security-Policy" "X-Frame-Options" "X-Content-Type-Options" "Referrer-Policy"; do
    if ! grep -qi "^$h:" <<<"$headers"; then
      echo "MANQUANT : $h sur $url"
      FAIL=1
    fi
  done
}

check_headers "$BASE/"
check_headers "$BASE/index.html"
ASSET="$(curl -s "$BASE/" | grep -oE '/assets/[^"]+\.js' | head -n1 || true)"
if [ -n "$ASSET" ]; then check_headers "$BASE$ASSET"; fi
check_headers "$BASE/api/health"

code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/health")"
[ "$code" = "200" ] || { echo "ÉCHEC : /api/health renvoie $code"; FAIL=1; }

ctype="$(curl -s -o /dev/null -w '%{content_type}' "$BASE/api/xyz")"
case "$ctype" in
  application/json*) ;;
  *) echo "ÉCHEC : /api/xyz ne renvoie pas une erreur JSON de l'API ($ctype)"; FAIL=1 ;;
esac

exit "$FAIL"
