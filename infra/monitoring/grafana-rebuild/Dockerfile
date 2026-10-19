# Experimental core-only rebuild: not selected by production or release scanning.
# Does not repair the 13 separately distributed datasource binaries.
FROM golang:1.27.2-alpine@sha256:f92b6ef800e499660581efdabdf25d9d817a9d124eaf900924f0504e7e27e12d AS build
RUN apk add --no-cache build-base patch
ADD --checksum=sha256:fdd57503b5f591e951ea3dff80ab53a41487c3373dc89370da2e36e7bf752f52 https://codeload.github.com/grafana/grafana/tar.gz/refs/tags/v13.2.4 /tmp/source.tar.gz
RUN mkdir /src && tar -xzf /tmp/source.tar.gz --strip-components=1 -C /src
WORKDIR /src
COPY dependencies.patch /tmp/dependencies.patch
RUN patch --batch --fuzz=0 --dry-run -p1 < /tmp/dependencies.patch \
    && patch --batch --fuzz=0 -p1 < /tmp/dependencies.patch
ENV GOWORK=off GOMAXPROCS=2
RUN --mount=type=cache,id=evidenceai-grafana-mod,target=/go/pkg/mod \
    --mount=type=cache,id=evidenceai-grafana-build,target=/root/.cache/go-build \
    test "$(go list -mod=readonly -m -f '{{.Version}}' github.com/getkin/kin-openapi)" = v0.149.0 \
    && test "$(go list -mod=readonly -m -f '{{.Version}}' github.com/santhosh-tekuri/jsonschema/v6)" = v6.0.3 \
    && CGO_ENABLED=1 go build -mod=readonly -p=2 -tags=oss -trimpath -buildvcs=false \
    -ldflags="-s -w -buildid= -X main.version=13.2.4 -X main.commit=af4a33e3786594ad72f72d97e6744010330c2977 -X main.buildBranch=evidenceai-security-experiment" \
    -o /out/grafana ./pkg/cmd/grafana \
    && printf '%s\n' 'UNAPPROVED EXPERIMENT: not vendor build parity or a signed attestation' \
       'source_tag=v13.2.4' 'source_commit=af4a33e3786594ad72f72d97e6744010330c2977' \
       > /out/evidenceai-build.txt \
    && go version >> /out/evidenceai-build.txt \
    && go version -m /out/grafana >> /out/evidenceai-build.txt \
    && sha256sum /tmp/source.tar.gz /tmp/dependencies.patch go.mod go.sum /out/grafana >> /out/evidenceai-build.txt
FROM grafana/grafana@sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f
LABEL org.opencontainers.image.source="https://github.com/grafana/grafana" \
      org.opencontainers.image.revision="af4a33e3786594ad72f72d97e6744010330c2977" \
      org.opencontainers.image.version="13.2.4-evidenceai-m123-experiment"
COPY --from=build /out/grafana /usr/share/grafana/bin/grafana
COPY --from=build /out/evidenceai-build.txt /usr/share/grafana/evidenceai-build.txt
