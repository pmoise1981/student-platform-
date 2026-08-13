#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
cp -n .env.example .env || true
docker compose up -d postgres
alembic upgrade head
python - <<'PY'
from app.db import SessionLocal
from app.services.templates import seed_templates
with SessionLocal() as db: seed_templates(db)
PY
