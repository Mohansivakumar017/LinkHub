# Security Policy

## Supported versions

Only the latest commit on `main` is supported. This repository is an active
prototype and should not be exposed to the public internet without the
production deployment controls described in the README.

## Reporting a vulnerability

Do not open a public issue for a security vulnerability. Use GitHub's private
security advisory workflow for this repository, or contact the repository
maintainer privately with:

- affected component and endpoint;
- reproduction steps or a minimal proof of concept;
- impact and suggested severity;
- any relevant logs with secrets and personal data removed.

Please allow reasonable time for investigation and remediation before public
disclosure. Never include credentials, tokens, production data, or private
user information in a report.

## Security expectations

- Never commit `.env` files, credentials, access tokens, or real secrets.
- Run the backend tests, frontend tests, lint, type checks, and Gitleaks scan
  before submitting a change.
- Keep production infrastructure behind the production Compose overlay and a
  TLS reverse proxy.
- Keep `/metrics`, PostgreSQL, Redis, Grafana, and Mailpit private.
