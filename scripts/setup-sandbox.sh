#!/usr/bin/env bash
# Idempotent environment setup: PostgreSQL, .env, dependencies, migrations.
# Used by the agent platform for every new sandbox and works on a developer machine too.
# With a working Docker daemon it starts the `db` service from docker-compose.yml,
# otherwise it installs/starts PostgreSQL via apt.
set -euo pipefail

cd "$(dirname "$0")/.."

DB_USER=app
DB_PASSWORD=app
DB_NAME=app

log() { printf '\n==> %s\n' "$*"; }

as_root() {
  if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo -n "$@"; fi
}

start_postgres_with_docker() {
  log "Starting PostgreSQL via docker compose"
  docker compose up -d --wait db
}

start_postgres_with_apt() {
  if ! command -v pg_lsclusters >/dev/null 2>&1; then
    log "Installing PostgreSQL via apt"
    as_root apt-get update -y
    as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y postgresql
  fi

  local version cluster
  read -r version cluster _ < <(pg_lsclusters --no-header | head -n1)
  if [ -z "${version:-}" ]; then
    log "Creating PostgreSQL cluster"
    version=$(ls /usr/lib/postgresql | sort -V | tail -n1)
    cluster=main
    as_root pg_createcluster "$version" "$cluster"
  fi
  log "Starting PostgreSQL $version/$cluster"
  as_root pg_ctlcluster "$version" "$cluster" start 2>/dev/null || true
  for _ in $(seq 1 30); do
    pg_isready -h localhost -p 5432 -q && break
    sleep 1
  done
  pg_isready -h localhost -p 5432

  log "Ensuring role '$DB_USER' and database '$DB_NAME'"
  as_root su postgres -c "psql -v ON_ERROR_STOP=1 -q" <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DB_USER') THEN
    CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASSWORD' CREATEDB;
  END IF;
END
\$\$;
SELECT 'CREATE DATABASE $DB_NAME OWNER $DB_USER'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec
SQL
}

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  start_postgres_with_docker
else
  start_postgres_with_apt
fi

if [ ! -f .env ]; then
  log "Creating .env from .env.example"
  cp .env.example .env
fi

log "Installing dependencies"
make install

log "Applying migrations"
make migrate

log "Setup complete. Run 'make check' to verify, 'make dev' to start."
