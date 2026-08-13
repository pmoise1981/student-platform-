from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/")
def root():
    return {
        "message": "Your FastAPI environment is ready.",
        "postgres_host": os.getenv("DATABASE_HOST", "postgres"),
        "redis_host": os.getenv("REDIS_HOST", "redis"),
    }

@app.get("/health")
def health():
    return {"status": "ok"}
