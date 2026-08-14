import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Student Backend Environment")


@app.get("/", response_class=HTMLResponse)
def root():
    postgres_host = os.getenv("DATABASE_HOST", "postgres")
    redis_host = os.getenv("REDIS_HOST", "redis")
    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Your Backend Environment</title>
        <style>
          body {{ font-family: system-ui, sans-serif; max-width: 720px; margin: 64px auto; padding: 0 20px; line-height: 1.5; }}
          .card {{ border: 1px solid #ddd; border-radius: 12px; padding: 24px; }}
          .ok {{ color: #16794b; font-weight: 700; }}
          a {{ display: inline-block; margin-right: 16px; }}
          code {{ background: #f3f3f3; padding: 2px 6px; border-radius: 5px; }}
        </style>
      </head>
      <body>
        <div class="card">
          <h1>Backend environment ready</h1>
          <p class="ok">FastAPI is running.</p>
          <p>Your environment includes PostgreSQL and Redis on the internal service network.</p>
          <p><strong>PostgreSQL host:</strong> <code>{postgres_host}</code><br>
             <strong>Redis host:</strong> <code>{redis_host}</code></p>
          <p><a href="/docs">Open API Docs</a><a href="/health">Health Check</a></p>
        </div>
      </body>
    </html>
    """


@app.get("/health")
def health():
    return {"status": "ok"}
