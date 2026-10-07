#!/bin/bash
# Runs once, after pagila is loaded. The MCP SQL tools connect as lexlens_ro only.
set -euo pipefail
psql -v ON_ERROR_STOP=1 -v ro_pw="$SAMPLE_DB_RO_PASSWORD" --username postgres --dbname pagila <<'SQL'
CREATE EXTENSION IF NOT EXISTS hypopg;
CREATE ROLE lexlens_ro LOGIN PASSWORD :'ro_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE pagila TO lexlens_ro;
GRANT USAGE ON SCHEMA public TO lexlens_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO lexlens_ro;
GRANT EXECUTE ON FUNCTION hypopg_create_index(text), hypopg_reset(), hypopg_hide_index(oid) TO lexlens_ro;
ALTER ROLE lexlens_ro SET default_transaction_read_only = on;
ALTER ROLE lexlens_ro SET statement_timeout = '5s';
SQL
