#!/bin/sh
set -eu
if [ "$(id -u)" != 999 ]; then
  echo 'Database startup requires the dedicated UID 999; root privilege switching is unsupported.' >&2
  exit 1
fi
# Never reuse a Debian/glibc cluster by changing an image reference. Logical
# restore into a fresh Alpine volume is mandatory (locale/index compatibility).
if [ -s "${PGDATA}/PG_VERSION" ] && [ ! -f "${PGDATA}/.evidenceai-alpine-v1" ]; then
  echo 'Database startup refused: initialize a fresh compatible volume and perform a verified logical restore.' >&2
  exit 1
fi
exec /usr/local/bin/docker-entrypoint.sh "$@"
