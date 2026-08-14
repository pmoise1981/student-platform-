#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt

if [ ! -f .env ]; then
  cp .env.example .env
else
  # Migrate the original local default from 5432 to the platform's dedicated 5433 port.
  sed -i 's#localhost:5432/platform#localhost:5433/platform#' .env
fi

docker compose up -d postgres

until docker compose exec -T postgres pg_isready -U platform -d platform >/dev/null 2>&1; do
  sleep 1
done

alembic upgrade head
python - <<'PY'
from app.db import SessionLocal
from app.services.templates import seed_templates

with SessionLocal() as db:
    seed_templates(db)

print("Templates seeded successfully")
PY
