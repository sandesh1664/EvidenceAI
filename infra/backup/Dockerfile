FROM python:3.14.6-alpine@sha256:26730869004e2b9c4b9ad09cab8625e81d256d1ce97e72df5520e806b1709f92
# Distribution-supported PostgreSQL 17 clients; no copied glibc libraries or server volume.
RUN apk upgrade --no-cache && apk add --no-cache age ca-certificates postgresql17-client && addgroup -g 10001 evidenceai && adduser -D -H -u 10001 -G evidenceai evidenceai && mkdir -p /work /backups && chown 10001:10001 /work /backups
COPY backup.py /opt/backup.py
USER 10001:10001
WORKDIR /work
ENTRYPOINT ["python", "/opt/backup.py"]
CMD ["backup"]
