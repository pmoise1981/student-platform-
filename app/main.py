import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import auth, environments, system, templates
from app.config import get_settings
from app.observability.logging import configure_logging
from app.observability.metrics import HTTP_DURATION, HTTP_REQUESTS

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title="Student Platform", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router, prefix="/api")
app.include_router(templates.router, prefix="/api")
app.include_router(environments.router, prefix="/api")
app.include_router(system.router)


@app.middleware("http")
async def request_metrics(request: Request, call_next):
    start = time.perf_counter()
    request.state.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    HTTP_REQUESTS.labels(request.method, path, response.status_code).inc()
    HTTP_DURATION.labels(request.method, path).observe(time.perf_counter() - start)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


frontend = Path(__file__).resolve().parent.parent / "frontend"
if frontend.exists():
    app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
