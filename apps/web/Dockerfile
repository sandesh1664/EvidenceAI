# syntax=docker/dockerfile:1
ARG NODE_IMAGE=node:26-bookworm-slim@sha256:298992629d69bbd5b2b03ad57094d8e4fcb3a8eeb7c4e25d29de656519568913
FROM ${NODE_IMAGE} AS base
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
FROM base AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
FROM dependencies AS build
ENV NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_API_BASE_URL=same-origin
COPY . .
RUN npm run build
FROM base AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_API_BASE_URL=same-origin PORT=3000 HOSTNAME=0.0.0.0
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack
RUN groupadd --gid 10001 evidenceai && useradd --uid 10001 --gid 10001 --no-create-home evidenceai
WORKDIR /app
COPY --from=build --chown=10001:10001 /app/.next/standalone ./
COPY --from=build --chown=10001:10001 /app/.next/static ./.next/static
COPY --from=build --chown=10001:10001 /app/public ./public
USER 10001:10001
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD node -e "fetch('http://127.0.0.1:3000/login').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.js"]
