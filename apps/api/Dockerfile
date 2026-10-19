# syntax=docker/dockerfile:1
ARG PYTHON_IMAGE=python:3.14.6-slim-trixie@sha256:7bec7ddcddeff7975d6ba9b4be7dd6f6b2f55e7491539145e2978f7f97ce9144
FROM ${PYTHON_IMAGE} AS base
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
FROM base AS dependencies
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir --only-binary=:all: -r requirements.txt && /opt/venv/bin/pip check
FROM base AS runtime
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd --gid 10001 evidenceai && useradd --uid 10001 --gid 10001 --no-create-home evidenceai && mkdir -p /app /data/documents /metrics && chown -R 10001:10001 /app /data /metrics && chmod 700 /data/documents
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
