# Isolated 12.4.13 experiment. Never selected by production; no vulnerability waivers.
FROM golang:1.27.2-alpine@sha256:f92b6ef800e499660581efdabdf25d9d817a9d124eaf900924f0504e7e27e12d AS source
RUN apk add --no-cache build-base patch
ADD --checksum=sha256:53fb4872e64de5a9a626ef9acd60b4b84c59a54394587f488dba6bff76299924 https://codeload.github.com/grafana/grafana/tar.gz/refs/tags/v12.4.13 /tmp/source.tar.gz
RUN mkdir /src && tar -xzf /tmp/source.tar.gz --strip-components=1 -C /src
WORKDIR /src
COPY dependencies-124.patch /tmp/dependencies.patch
RUN patch --batch --fuzz=0 --dry-run -p1 < /tmp/dependencies.patch \
    && patch --batch --fuzz=0 -p1 < /tmp/dependencies.patch
ENV GOMAXPROCS=2
FROM source AS tempo-probe
RUN --mount=type=cache,id=evidenceai-grafana-mod,target=/go/pkg/mod \
    GOWORK=off GOPROXY=https://proxy.golang.org go get github.com/grafana/tempo@v2.10.3
FROM source AS build
RUN --mount=type=cache,id=evidenceai-grafana-mod,target=/go/pkg/mod \
    --mount=type=cache,id=evidenceai-grafana-build,target=/root/.cache/go-build \
    test "$(go list -mod=readonly -m -f '{{.Version}}' github.com/getkin/kin-openapi)" = v0.149.0 \
    && CGO_ENABLED=1 go build -mod=readonly -p=2 -tags=oss -trimpath -buildvcs=false \
    -ldflags="-s -w -buildid= -X main.version=12.4.13 -X main.commit=bbc0a79c71a946c1fd61ee4f9e0fcba812c18bd7 -X main.buildBranch=evidenceai-security-experiment" \
    -o /out/grafana ./pkg/cmd/grafana \
    && printf '%s\n' 'UNAPPROVED EXPERIMENT; vendor patched-source parity not established' \
       'source_tag=v12.4.13' 'source_commit=bbc0a79c71a946c1fd61ee4f9e0fcba812c18bd7' > /out/evidenceai-build.txt \
    && go version >> /out/evidenceai-build.txt \
    && go version -m /out/grafana >> /out/evidenceai-build.txt \
    && sha256sum /tmp/source.tar.gz /tmp/dependencies.patch go.mod go.sum /out/grafana >> /out/evidenceai-build.txt
FROM grafana/grafana@sha256:41bbc1b5e04416f81891806076db2a2ff60a5d4da5f78d36a88b033a8c199185 AS candidate
LABEL org.opencontainers.image.source="https://github.com/grafana/grafana" \
      org.opencontainers.image.revision="bbc0a79c71a946c1fd61ee4f9e0fcba812c18bd7" \
      org.opencontainers.image.version="12.4.13-evidenceai-m124-experiment"
COPY --from=build /out/grafana /usr/share/grafana/bin/grafana
COPY --from=build /out/evidenceai-build.txt /usr/share/grafana/evidenceai-build.txt
