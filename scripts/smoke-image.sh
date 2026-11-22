#!/usr/bin/env bash
# The smoke test of a built image (tasks 3.1 and 3.2), run by CI on Linux:
# what the image holds, then the image upgrading a real database and serving.
#
#   SMOKE_DATABASE_URL=postgresql://owner:secret@localhost:5432/db scripts/smoke-image.sh fcon:ci
#
# SMOKE_DATABASE_URL is the owner's address of a Postgres reachable from
# `--network host`. Linux only: Docker Desktop has no host network.
set -euo pipefail

image="${1:?usage: scripts/smoke-image.sh <image>}"
database_url="${SMOKE_DATABASE_URL:?set SMOKE_DATABASE_URL to the owner address of a Postgres}"
container=fcon-smoke
# Not the default 8080: the health check must follow the host's port.
port=9090
base="http://127.0.0.1:${port}"

cleanup() {
    status=$?
    if [ "$status" -ne 0 ] && docker container inspect "$container" >/dev/null 2>&1; then
        echo "--- the server's log ---"
        docker logs "$container" || true
    fi
    docker rm -f "$container" >/dev/null 2>&1 || true
    exit "$status"
}
trap cleanup EXIT

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

echo "== what ${image} holds"
docker run --rm --entrypoint sh "$image" -c '
    set -eu
    problems=0
    if [ "$(id -u)" = 0 ]; then echo "runs as root"; problems=1; fi
    echo "check: runs as uid $(id -u)"
    for tool in uv uvx gcc cc; do
        if command -v "$tool" >/dev/null 2>&1; then echo "holds $tool"; problems=1; fi
    done
    echo "check: no uv, uvx, gcc or cc"
    found=$(find / -xdev \( -name .env -o -name .git \) -print 2>/dev/null || true)
    if [ -n "$found" ]; then echo "holds: $found"; problems=1; fi
    echo "check: no .env and no .git"
    tests=$(find /app/.venv -type d -path "*/fcon_*/tests" -print 2>/dev/null || true)
    if [ -n "$tests" ]; then echo "holds our tests: $tests"; problems=1; fi
    echo "check: no tests directory under an fcon_* package"
    exit "$problems"
' || fail "the image holds what it must not"

echo "== fcon db upgrade"
docker run --rm --network host -e FCON_DATABASE_URL="$database_url" "$image" db upgrade \
    || fail "fcon db upgrade did not succeed"

echo "== the server on port ${port}"
docker run -d --name "$container" --network host \
    -e FCON_DATABASE_URL="$database_url" -e FCON_SECRET_KEY="$(openssl rand -hex 32)" -e PORT="$port" "$image" >/dev/null

health=starting
for _ in $(seq 1 60); do
    health=$(docker inspect --format '{{.State.Health.Status}}' "$container")
    [ "$health" = healthy ] && break
    [ "$(docker inspect --format '{{.State.Running}}' "$container")" = true ] \
        || fail "the server stopped"
    sleep 1
done
[ "$health" = healthy ] || fail "the health check says ${health} after 60 s"
echo "check: Docker reports the container healthy"

body=$(curl -fsS "${base}/healthz") || fail "/healthz did not answer"
grep -q '"alive"' <<<"$body" || fail "/healthz said: ${body}"
echo "check: /healthz says alive"

body=$(curl -fsS "${base}/readyz") || fail "/readyz did not answer 200"
grep -q '"ready"' <<<"$body" || fail "/readyz said: ${body}"
echo "check: /readyz says ready"

body=$(curl -fsS "${base}/sign-in") || fail "/sign-in did not answer 200"
grep -q 'Feather Connect' <<<"$body" || fail "/sign-in does not show Feather Connect"
echo "check: /sign-in shows Feather Connect"

echo "== the image passed the smoke test"
