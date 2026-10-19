# syntax=docker/dockerfile:1
ARG PYTHON_IMAGE=python:3.14.6-alpine@sha256:26730869004e2b9c4b9ad09cab8625e81d256d1ce97e72df5520e806b1709f92
FROM ${PYTHON_IMAGE} AS base
RUN apk upgrade --no-cache
FROM base AS dependencies
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir --only-binary=:all: -r requirements.txt && /opt/venv/bin/pip check
FROM base AS runtime
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN addgroup -g 10001 evidenceai && adduser -D -H -u 10001 -G evidenceai evidenceai && mkdir -p /app /data/documents /metrics && chown -R 10001:10001 /app /data /metrics && chmod 700 /data/documents
WORKDIR /app
COPY --from=dependencies /opt/venv /opt/venv
RUN /opt/venv/bin/pip uninstall -y pytest iniconfig pluggy Pygments && /opt/venv/bin/pip check
COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 alembic ./alembic
COPY --chown=10001:10001 alembic.ini .
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health',timeout=3)"
ENTRYPOINT ["python", "-m", "app.container_entrypoint"]
CMD ["api"]
