FROM golang:1.27.2-alpine@sha256:f92b6ef800e499660581efdabdf25d9d817a9d124eaf900924f0504e7e27e12d AS build
ADD --checksum=sha256:a90f1df0fde58d216d4a7d342e64831d2e3257db8084deadbe69754d34b15142 https://codeload.github.com/prometheus/node_exporter/tar.gz/refs/tags/v1.12.1 /tmp/source.tar.gz
RUN mkdir /src && tar -xzf /tmp/source.tar.gz --strip-components=1 -C /src
WORKDIR /src
COPY go.mod go.sum ./
RUN CGO_ENABLED=0 go build -mod=readonly -trimpath -buildvcs=false -ldflags="-s -w -buildid= -X github.com/prometheus/common/version.Version=1.12.1-evidenceai" -o /out/node_exporter .
FROM prom/node-exporter@sha256:1b4e4438faca4dd7e001dd445d161a4a2091b0fededa84093b3a8dfeae1f1be0
COPY --from=build /out/node_exporter /bin/node_exporter
