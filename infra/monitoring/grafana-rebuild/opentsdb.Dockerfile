# Official, signed OpenTSDB plugin upgrade; retains all bundled datasources.
ARG TARGETARCH
FROM scratch AS download-arm64
ADD --checksum=sha256:089b71a3c576dec39003ae809902428d54462c05d58d39a50f075f1180567859 https://grafana.com/api/plugins/opentsdb/versions/13.0.5/download?os=linux&arch=arm64 /plugin.zip
FROM scratch AS download-amd64
ADD --checksum=sha256:ae51e0a76901de07860777f5b992fe3924206181f4c99287a9d840710682bf24 https://grafana.com/api/plugins/opentsdb/versions/13.0.5/download?os=linux&arch=amd64 /plugin.zip
FROM download-${TARGETARCH} AS download
FROM grafana/grafana@sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f AS extract
USER root
COPY --from=download /plugin.zip /tmp/plugin.zip
RUN mkdir /out && unzip -q /tmp/plugin.zip -d /out && test -f /out/opentsdb/MANIFEST.txt
FROM grafana/grafana@sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f
COPY --from=extract --chown=472:0 /out/opentsdb/ /usr/share/grafana/data/plugins-bundled/opentsdb/
