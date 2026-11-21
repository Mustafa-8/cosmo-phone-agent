#!/usr/bin/env bash
# Put the COSMO demo online from this laptop: build the website, start the combined server
# (agent + voice + website on one port) and open a public HTTPS Cloudflare quick tunnel.
#
#   ./run_online.sh            # Ctrl+C stops everything
#
# Needs: .env with ELEVENLABS_API_KEY and GOOGLE_API_KEY, .venv with requirements.txt,
# Node 20.19+ and cloudflared on PATH. The link changes every time you start it.
# Anyone with the link can use the demo (and your API credits) while this runs.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/node/bin:$HOME/.local/bin:$PATH"
PORT="${PORT:-8080}"
PY="${PYTHON:-.venv/bin/python}"

[ -f .env ] || { echo "Missing .env (copy .env.example and add the keys)"; exit 1; }
command -v cloudflared >/dev/null || { echo "cloudflared not found"; exit 1; }

echo "==> Building the website (same-origin API URLs)"
(cd frontend && { [ -d node_modules ] || npm ci --no-audit --no-fund; } && VITE_AGENT_URL= VITE_VOICE_URL=/voice npm run build >/dev/null)

echo "==> Starting the server on port $PORT"
PORT="$PORT" "$PY" serve.py &
SERVER=$!
LOG="$(mktemp)"
trap 'kill $SERVER ${TUNNEL:-} 2>/dev/null; rm -f "$LOG"' EXIT
for _ in $(seq 60); do curl -fs "http://127.0.0.1:$PORT/voice/health" >/dev/null && break; sleep 0.5; done
curl -fs "http://127.0.0.1:$PORT/voice/health" >/dev/null || { echo "Server did not start"; exit 1; }

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
echo "  (local: http://localhost:$PORT)   Ctrl+C to stop"
echo
wait $SERVER
