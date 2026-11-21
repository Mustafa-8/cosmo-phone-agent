#!/usr/bin/env bash
# Put the COSMO demo online from this laptop: build the website, start the combined server
# (agent + voice + website on one port) and open a public HTTPS Cloudflare quick tunnel.
#
#   ./run_online.sh            # Ctrl+C stops everything
#
# Needs: .env with ELEVENLABS_API_KEY and GOOGLE_API_KEY, .venv with requirements.txt,
# Node 20.19+ and cloudflared on PATH. The link changes every time you start it.
# The site needs an access code (demo_access.py): set DEMO_ACCESS_CODE in .env, or a random
# one is made and printed below. Share the link and the code only with people who should use it.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/node/bin:$HOME/.local/bin:$PATH"
PORT="${PORT:-8080}"
PY="${PYTHON:-.venv/bin/python}"
# Read DEMO_ACCESS_CODE from .env if present; otherwise make a random one for this run.
if [ -z "${DEMO_ACCESS_CODE:-}" ] && [ -f .env ]; then
  DEMO_ACCESS_CODE="$(grep -E '^DEMO_ACCESS_CODE=' .env | tail -1 | cut -d= -f2- || true)"
fi
if [ -z "${DEMO_ACCESS_CODE:-}" ]; then
  DEMO_ACCESS_CODE="$("$PY" -c 'import secrets; print(secrets.token_urlsafe(6))')"
fi
export DEMO_ACCESS_CODE

[ -f .env ] || { echo "Missing .env (copy .env.example and add the keys)"; exit 1; }
command -v cloudflared >/dev/null || { echo "cloudflared not found"; exit 1; }

echo "==> Building the website (same-origin API URLs)"
(cd frontend && { [ -d node_modules ] || npm ci --no-audit --no-fund; } && VITE_AGENT_URL= VITE_VOICE_URL=/voice npm run build >/dev/null)

if curl -s -o /dev/null "http://127.0.0.1:$PORT/"; then
  echo "Port $PORT is already in use (another COSMO server still running?)."
  echo "Stop it, or start on another port:  PORT=8081 ./run_online.sh"
  exit 1
fi

echo "==> Starting the server on port $PORT"
PORT="$PORT" "$PY" serve.py &
SERVER=$!
LOG="$(mktemp)"
trap 'kill $SERVER ${TUNNEL:-} 2>/dev/null; rm -f "$LOG"' EXIT
# Readiness: the website (/) is public, everything else needs the access code (demo_access.py),
# so check the home page, not /voice/health (that one answers 401 without the code).
for _ in $(seq 60); do
  kill -0 "$SERVER" 2>/dev/null || { echo "Server exited during startup (see errors above)"; exit 1; }
  curl -fs "http://127.0.0.1:$PORT/" >/dev/null && break
  sleep 0.5
done
curl -fs "http://127.0.0.1:$PORT/" >/dev/null && kill -0 "$SERVER" 2>/dev/null \
  || { echo "Server did not start"; exit 1; }

echo "==> Opening the public tunnel"
cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" >"$LOG" 2>&1 &
TUNNEL=$!
URL=""
for _ in $(seq 60); do
  URL="$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG" | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 0.5
done
[ -n "$URL" ] || { echo "Tunnel failed:"; tail -20 "$LOG"; exit 1; }

echo
echo "  COSMO is online:  $URL"
echo "  Access code:      $DEMO_ACCESS_CODE"
echo "  (local: http://localhost:$PORT)   Ctrl+C to stop"
echo
wait $SERVER
