#!/usr/bin/env sh
set -eu
alembic upgrade head
python -c "from app.db import SessionLocal; from app.services.templates import seed_templates; db=SessionLocal(); seed_templates(db); db.close()"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
