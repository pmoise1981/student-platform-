import os

from fastapi import FastAPI
from psycopg import connect
from redis import Redis

app = FastAPI(title="My Student Backend")

DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.environ["REDIS_URL"]


@app.get("/")
def root():
    return {"message": "Your backend workspace is live. Edit app/main.py and save."}


@app.get("/dependencies")
def dependencies():
    with connect(DATABASE_URL) as conn:
        database_ok = conn.execute("select 1").fetchone()[0] == 1
    redis_ok = Redis.from_url(REDIS_URL).ping()
    return {"postgres": database_ok, "redis": bool(redis_ok)}


@app.get("/health")
def health():
    return {"status": "ok"}
