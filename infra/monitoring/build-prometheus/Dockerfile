FROM node:26-alpine@sha256:6f08a523443ddedf52941874c203475b0ad503e859ad70cb26ab8be9a517dbd5 AS ui
RUN apk add --no-cache bash && npm install -g pnpm@10.34.7
ADD --checksum=sha256:d6383dea2f9b26c1673a52859c453653f2c6c046f7fb6d01db59603a65a732eb https://codeload.github.com/prometheus/prometheus/tar.gz/refs/tags/v3.15.0 /tmp/source.tar.gz
RUN mkdir /src && tar -xzf /tmp/source.tar.gz --strip-components=1 -C /src
WORKDIR /src/web/ui
RUN pnpm install --frozen-lockfile && cd react-app && pnpm install --frozen-lockfile
RUN pnpm run build
FROM golang:1.27.2-alpine@sha256:f92b6ef800e499660581efdabdf25d9d817a9d124eaf900924f0504e7e27e12d AS build
ADD --checksum=sha256:d6383dea2f9b26c1673a52859c453653f2c6c046f7fb6d01db59603a65a732eb https://codeload.github.com/prometheus/prometheus/tar.gz/refs/tags/v3.15.0 /tmp/source.tar.gz
RUN mkdir /src && tar -xzf /tmp/source.tar.gz --strip-components=1 -C /src
WORKDIR /src
COPY go.mod go.sum ./
# UI assets are retained on disk, outside /prometheus's writable data mount.
RUN CGO_ENABLED=0 go build -mod=readonly -tags=netgo -trimpath -buildvcs=false -ldflags="-s -w -buildid= -X github.com/prometheus/common/version.Version=3.15.0-evidenceai" -o /out/prometheus ./cmd/prometheus && CGO_ENABLED=0 go build -mod=readonly -trimpath -buildvcs=false -ldflags="-s -w -buildid=" -o /out/promtool ./cmd/promtool
FROM prom/prometheus@sha256:efd719c99d83b060d9daefdcf00360461adf279f45ef5391f8d111892118753e
COPY --from=build /out/prometheus /bin/prometheus
COPY --from=build /out/promtool /bin/promtool
COPY --from=ui /src/web/ui/static /usr/share/prometheus/ui/static
WORKDIR /usr/share/prometheus
