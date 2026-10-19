# Same PostgreSQL major/minor and pgvector release; supported musl/libxml2 runtime.
FROM postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24 AS build
RUN apk add --no-cache build-base
ADD --checksum=sha256:cac0b10c360f05b2d521200105ba3697e773d4cd3731f5a915a7e37ebe0bea85 https://codeload.github.com/pgvector/pgvector/tar.gz/refs/tags/v0.8.7 /tmp/pgvector.tar.gz
RUN tar -xzf /tmp/pgvector.tar.gz -C /tmp && cd /tmp/pgvector-0.8.7 && make OPTFLAGS="" with_llvm=no && make install with_llvm=no
FROM postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24
# Production is strictly UID 999. The unused root-only privilege-switching
# executable embeds vulnerable Go; remove it rather than pretending apk fixes it.
RUN rm -f /usr/local/bin/gosu && apk upgrade --no-cache && sed -i 's/postgres:x:70:70:/postgres:x:999:999:/' /etc/passwd && sed -i 's/postgres:x:70:/postgres:x:999:/' /etc/group && chown -R 999:999 /var/lib/postgresql /var/run/postgresql
COPY --from=build /usr/local/lib/postgresql/vector.so /usr/local/lib/postgresql/vector.so
COPY --from=build /usr/local/share/postgresql/extension/vector* /usr/local/share/postgresql/extension/
COPY --from=build /tmp/pgvector-0.8.7/LICENSE /usr/share/doc/pgvector/LICENSE
COPY entrypoint.sh /usr/local/bin/evidenceai-db-entrypoint
COPY 00-runtime-marker.sh /docker-entrypoint-initdb.d/00-runtime-marker.sh
USER 999:999
ENTRYPOINT ["/usr/local/bin/evidenceai-db-entrypoint"]
CMD ["postgres"]
