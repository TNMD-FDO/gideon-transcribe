#!/usr/bin/env bash
# Does the media route serve part of a file, or only the whole of it?
#
# A browser jumps about in a video by asking for a range of bytes. If the
# server answers the whole file instead, the video plays from the start and
# cannot be scrubbed, which looks exactly like a broken page and is not one.
# Nothing else in this repository proves that it works, and the media route
# has already been wrong once in a way nobody could see.
#
# This runs the real Caddyfile against a stand-in for the app and a file of
# known bytes, asks for the middle hundred of them, and fails unless it gets
# a 206 with exactly those hundred bytes back. It needs Docker and nothing
# else, and it leaves nothing behind.
#
#   ./caddy/check-ranges.sh
set -euo pipefail

CADDY_IMAGE="${CADDY_IMAGE:-caddy:2.11-alpine}"
PORT="${PORT:-8443}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

WORK="$(mktemp -d)"
NAME="caddy-range-check-$$"
STUB=""

tidy_up() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  [ -n "$STUB" ] && kill "$STUB" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap tidy_up EXIT

fail() { printf '\033[31mFAIL\033[0m  %s\n' "$1"; exit 1; }
pass() { printf '\033[32mpass\033[0m  %s\n' "$1"; }

# The two folders Caddy is given, each with a file of known bytes.
WORKSPACE_ID="11111111-1111-4111-8111-111111111111"
CASE_ID="22222222-2222-4222-8222-222222222222"
CASE_RECORDING="33333333-3333-4333-8333-333333333333"

mkdir -p "$WORK/scratch/6/$WORKSPACE_ID"
mkdir -p "$WORK/cases/$CASE_ID/$CASE_RECORDING"
# A megabyte of a repeating pattern, so the bytes that come back can be
# checked against the bytes that were asked for.
python3 -c "
import sys
sys.stdout.buffer.write(bytes(range(256)) * 4096)
" > "$WORK/scratch/6/$WORKSPACE_ID/playback.mp4"
cp "$WORK/scratch/6/$WORKSPACE_ID/playback.mp4" \
  "$WORK/cases/$CASE_ID/$CASE_RECORDING/playback.mp4"

# The certificate Caddy is told to use. Self-signed and thrown away with the
# rest: what is being checked is the range, not the trust.
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
  -keyout "$WORK/key.pem" -out "$WORK/cert.pem" \
  -subj "/CN=localhost" >/dev/null 2>&1

# A stand-in for the app, which says yes to every question about a file. What
# the real one answers is checked by its own tests; what is checked here is
# what Caddy does after it says yes.
python3 - <<'PYTHON' &
from http.server import BaseHTTPRequestHandler, HTTPServer


class Yes(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *arguments):
        pass


HTTPServer(("0.0.0.0", 8000), Yes).serve_forever()
PYTHON
STUB=$!

docker run -d --name "$NAME" \
  --add-host app:host-gateway \
  -e APP_HOSTNAME=localhost \
  -e ALLOWED_CLIENT_CIDRS=0.0.0.0/0 \
  -v "$HERE/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" \
  -v "$WORK/cert.pem:/etc/caddy/tls/cert.pem:ro" \
  -v "$WORK/key.pem:/etc/caddy/tls/key.pem:ro" \
  -v "$WORK/scratch:/srv/scratch:ro" \
  -v "$WORK/cases:/srv/cases:ro" \
  -p "$PORT:443" \
  "$CADDY_IMAGE" >/dev/null

# Caddy is up when it answers at all.
for _ in $(seq 1 40); do
  if curl -sk -o /dev/null "https://localhost:$PORT/media/6/$WORKSPACE_ID/playback.mp4"; then
    break
  fi
  sleep 0.5
done

check_one() {
  local what="$1" url="$2"

  local whole
  whole="$(curl -sk -o "$WORK/whole" -w '%{http_code}' "$url")"
  [ "$whole" = "200" ] || fail "$what: the whole file came back as $whole, not 200"
  [ "$(stat -c%s "$WORK/whole")" = "1048576" ] ||
    fail "$what: the whole file was not the size it should be"

  local code
  code="$(curl -sk -o "$WORK/part" -w '%{http_code}' -H 'Range: bytes=1000-1099' "$url")"
  if [ "$code" = "200" ]; then
    fail "$what: asked for 100 bytes and got the whole file. A browser cannot jump about in this: it needs 206 Partial Content."
  fi
  [ "$code" = "206" ] || fail "$what: asked for 100 bytes and got $code"

  local size
  size="$(stat -c%s "$WORK/part")"
  [ "$size" = "100" ] || fail "$what: asked for 100 bytes and got $size"

  # And the right hundred: byte 1000 of the pattern is 1000 modulo 256.
  local first
  first="$(python3 -c "
import sys
print(open(sys.argv[1], 'rb').read(1)[0])
" "$WORK/part")"
  [ "$first" = "$((1000 % 256))" ] ||
    fail "$what: the bytes that came back are not the bytes that were asked for"

  pass "$what serves 206 Partial Content, of the right bytes"
}

check_one "the Workspace media route" \
  "https://localhost:$PORT/media/6/$WORKSPACE_ID/playback.mp4"
check_one "the Case media route" \
  "https://localhost:$PORT/case-media/$CASE_ID/$CASE_RECORDING/playback.mp4"

echo
echo "A browser can jump about in a recording."
