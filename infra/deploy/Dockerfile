# Locked Go compiler and module graph remediate the upstream binary's Go/x/net CVEs.
FROM golang:1.27.2-alpine@sha256:f92b6ef800e499660581efdabdf25d9d817a9d124eaf900924f0504e7e27e12d AS build
WORKDIR /src
COPY caddy-build/go.mod caddy-build/go.sum ./
RUN go mod download
COPY caddy-build/main.go .
RUN CGO_ENABLED=0 go build -mod=readonly -trimpath -buildvcs=false -ldflags="-s -w -buildid=" -o /out/caddy .
FROM caddy@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f
# Replacing the executable also removes upstream file capabilities.
COPY --from=build /out/caddy /usr/bin/caddy
RUN chown -R 10001:10001 /data /config
USER 10001:10001
