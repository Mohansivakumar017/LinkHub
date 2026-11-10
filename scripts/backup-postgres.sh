#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${ROOT_DIR}/backups}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_PATH="${BACKUP_DIR}/linkhub-${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"
compose_args=(-f "${COMPOSE_FILE}")
if [[ -n "${COMPOSE_ENV_FILE}" ]]; then
  compose_args=(--env-file "${COMPOSE_ENV_FILE}" "${compose_args[@]}")
fi

docker compose "${compose_args[@]}" exec -T db \
  pg_dump --clean --if-exists --no-owner --no-privileges \
  -U "${POSTGRES_USER:-linkhub}" "${POSTGRES_DB:-linkhub}" \
  | gzip -9 > "${BACKUP_PATH}"

test -s "${BACKUP_PATH}"
printf 'Created PostgreSQL backup: %s\n' "${BACKUP_PATH}"
