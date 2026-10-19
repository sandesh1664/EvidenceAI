ARG POSTGRES_IMAGE=pgvector/pgvector@sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d
ARG PYTHON_IMAGE=python:3.14.6-slim-bookworm@sha256:4c92ffcde4dd6f1ff72a24518f49fd4990b27134987dfa31a733badde66df9f8
FROM ${POSTGRES_IMAGE} AS clients
RUN mkdir -p /opt/postgres/bin /opt/postgres/lib && cp /usr/lib/postgresql/17/bin/pg_dump /usr/lib/postgresql/17/bin/pg_restore /usr/lib/postgresql/17/bin/psql /opt/postgres/bin/ && ldd /opt/postgres/bin/* | awk '/=> \// {print $3}' | sort -u | xargs -I '{}' cp -L '{}' /opt/postgres/lib/
FROM ${PYTHON_IMAGE}
# This final image deliberately does not inherit the database server's VOLUME or entrypoint.
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends age ca-certificates && rm -rf /var/lib/apt/lists/* && groupadd -g 10001 evidenceai && useradd -u 10001 -g 10001 --no-create-home evidenceai && mkdir -p /work /backups && chown 10001:10001 /work /backups
COPY --from=clients /opt/postgres /opt/postgres
RUN for tool in pg_dump pg_restore psql; do printf '#!/bin/sh\nLD_LIBRARY_PATH=/opt/postgres/lib exec /opt/postgres/bin/%s "$@"\n' "$tool" > "/usr/local/bin/$tool"; chmod 755 "/usr/local/bin/$tool"; done
COPY backup.py /opt/backup.py
USER 10001:10001
WORKDIR /work
ENTRYPOINT ["python", "/opt/backup.py"]
CMD ["backup"]
