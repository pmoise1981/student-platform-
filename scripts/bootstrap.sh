#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt

# Keep local config aligned with the current example during first bootstrap.
if [ ! -f .env ]; then
  cp .env.example .env
fi

docker compose up -d postgres

# Wait for the control-plane database rather than racing Alembic against startup.
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
