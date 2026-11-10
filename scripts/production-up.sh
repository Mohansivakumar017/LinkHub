#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-${ROOT_DIR}/backend/.env.production}"

if [[ ! -f "${ENV_FILE}" ]]; then
  printf 'Missing production environment file: %s\n' "${ENV_FILE}" >&2
  printf 'Copy backend/.env.production.example and replace every placeholder.\n' >&2
  exit 1
fi

cd "${ROOT_DIR}"
docker compose \
  --env-file "${ENV_FILE}" \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  up -d --build
