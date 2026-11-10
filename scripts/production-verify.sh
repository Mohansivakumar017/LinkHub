#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-${ROOT_DIR}/backend/.env.production}"

if [[ ! -f "${ENV_FILE}" ]]; then
  printf 'Missing production environment file: %s\n' "${ENV_FILE}" >&2
  exit 1
fi

cd "${ROOT_DIR}"
docker compose \
  --env-file "${ENV_FILE}" \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  ps

curl --fail --silent --show-error http://127.0.0.1:8080/api/v1/ready
printf '\nProduction stack is ready.\n'
