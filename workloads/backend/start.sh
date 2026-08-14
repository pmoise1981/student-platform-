#!/usr/bin/env bash
set -euo pipefail

PROJECT=/home/coder/project
mkdir -p "$PROJECT"
if [ ! -f "$PROJECT/.initialized" ]; then
  cp -R /opt/student-template/starter/. "$PROJECT/"
  touch "$PROJECT/.initialized"
fi

cd "$PROJECT"
export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${DATABASE_HOST}:5432/${POSTGRES_DB}"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/student-fastapi.log 2>&1 &
exec code-server --bind-addr 0.0.0.0:8080 --auth password "$PROJECT"
