# Unapproved experiment: complete official signed plugin update, no capabilities removed.
ARG TARGETARCH
ARG BASE_IMAGE=grafana/grafana@sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f
FROM scratch AS download-arm64
ADD --checksum=sha256:5ac8bf252f415b5709c3e9f315919e1bdf152b70ee5b69c83bd9f1a1d41db0bd https://grafana.com/api/plugins/stackdriver/versions/12.6.3/download?os=linux&arch=arm64 /plugin.zip
FROM scratch AS download-amd64
ADD --checksum=sha256:3288d1bb06330449e7335346667ea7c74e5367c0d32390396c93ee54c89900cb https://grafana.com/api/plugins/stackdriver/versions/12.6.3/download?os=linux&arch=amd64 /plugin.zip
FROM download-${TARGETARCH} AS download
FROM grafana/grafana@sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f AS extract
USER root
COPY --from=download /plugin.zip /tmp/plugin.zip
RUN mkdir /out && unzip -q /tmp/plugin.zip -d /out && test -f /out/stackdriver/MANIFEST.txt
FROM ${BASE_IMAGE}
COPY --from=extract --chown=472:0 /out/stackdriver/ /usr/share/grafana/data/plugins-bundled/stackdriver/
LABEL io.evidenceai.experiment.stackdriver-version="12.6.3" \
      io.evidenceai.experiment.approval="UNAPPROVED"
