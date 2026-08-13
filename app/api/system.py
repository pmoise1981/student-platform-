from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from kubernetes.client import ApiException
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.kubernetes.client import KubernetesPlatform

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)):
    checks = {}
    try:
        db.execute(text("SELECT 1"))
        checks["postgresql"] = "ok"
    except Exception as exc:
        checks["postgresql"] = str(exc)
    try:
        KubernetesPlatform().ping()
        checks["kubernetes"] = "ok"
    except Exception as exc:
        checks["kubernetes"] = str(exc)
    if any(v != "ok" for v in checks.values()):
        raise HTTPException(status_code=503, detail=checks)
    return {"status": "ready", "checks": checks}


@router.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
