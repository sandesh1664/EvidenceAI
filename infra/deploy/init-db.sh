#!/bin/sh
set -eu
# Init scripts run only on a new deployment volume, never against development PGDATA.
export EVIDENCEAI_APP_PASSWORD="$(cat /run/secrets/db_password)"
psql --username postgres --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
\getenv app_password EVIDENCEAI_APP_PASSWORD
SELECT format('CREATE ROLE evidenceai LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L CONNECTION LIMIT 40', :'app_password') \gexec
CREATE DATABASE evidenceai OWNER evidenceai;
REVOKE ALL ON DATABASE evidenceai FROM PUBLIC;
SQL
psql --username postgres --dbname evidenceai --set ON_ERROR_STOP=1 <<'SQL'
CREATE EXTENSION vector;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO evidenceai;
SQL
unset EVIDENCEAI_APP_PASSWORD
