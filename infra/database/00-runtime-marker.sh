#!/bin/sh
set -eu
printf 'alpine-postgresql17-pgvector0.8.7\n' > "$PGDATA/.evidenceai-alpine-v1"
chmod 600 "$PGDATA/.evidenceai-alpine-v1"
