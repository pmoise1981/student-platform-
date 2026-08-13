import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import get_current_user
from app.db import get_db
from app.kubernetes.client import KubernetesPlatform
from app.models import Environment, EnvironmentStatus, JobAction, User
from app.schemas.core import CredentialsOut, EnvironmentCreate, EnvironmentDetail, EnvironmentOut, LogsOut
from app.services.environments import create_environment, enqueue_action

router = APIRouter(prefix="/environments", tags=["environments"])
log = logging.getLogger(__name__)


def owned_environment(db: Session, user: User, env_id: str) -> Environment:
    env = db.scalar(select(Environment).where(Environment.id == env_id, Environment.user_id == user.id))
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")
    return env


def serialize_detail(env: Environment) -> EnvironmentDetail:
    return EnvironmentDetail(
        **EnvironmentOut.model_validate(env).model_dump(),
        components=[{"name": d.component, "healthy": d.healthy, "message": d.last_message} for d in env.deployments],
    )


@router.post("", response_model=EnvironmentOut, status_code=202)
def provision(
    payload: EnvironmentCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    env, created = create_environment(db, user, payload, idempotency_key)
    if not created:
        response.status_code = 200
    return env


@router.get("", response_model=list[EnvironmentOut])
def list_environments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(Environment).where(Environment.user_id == user.id).order_by(Environment.created_at.desc())).all()


@router.get("/{env_id}", response_model=EnvironmentDetail)
def get_environment(env_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return serialize_detail(owned_environment(db, user, env_id))


@router.get("/{env_id}/status", response_model=EnvironmentDetail)
def status(env_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    env = owned_environment(db, user, env_id)
    if env.status in {EnvironmentStatus.running, EnvironmentStatus.provisioning}:
        try:
            health = KubernetesPlatform().health(env)
            known = {d.component: d for d in env.deployments}
            from app.models import Deployment
            for item in health:
                dep = known.get(item.name) or Deployment(environment_id=env.id, component=item.name)
                dep.healthy, dep.last_message = item.healthy, item.message
                db.add(dep)
            db.commit()
            db.refresh(env)
        except Exception as exc:
            log.warning("status_refresh_failed", extra={"environment_id": env.id, "error": str(exc)})
    return serialize_detail(env)


@router.post("/{env_id}/stop", response_model=EnvironmentOut, status_code=202)
def stop(env_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    env = owned_environment(db, user, env_id)
    if env.status in {EnvironmentStatus.deleting, EnvironmentStatus.deleted}:
        raise HTTPException(status_code=409, detail="Deleted environments cannot be stopped")
    enqueue_action(db, env, JobAction.stop)
    return env


@router.post("/{env_id}/start", response_model=EnvironmentOut, status_code=202)
def start(env_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    env = owned_environment(db, user, env_id)
    if env.status == EnvironmentStatus.deleted:
        raise HTTPException(status_code=409, detail="Deleted environments cannot be started")
    enqueue_action(db, env, JobAction.start)
    return env


@router.delete("/{env_id}", status_code=202)
def delete(env_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    env = owned_environment(db, user, env_id)
    enqueue_action(db, env, JobAction.delete)
    return {"detail": "Deletion queued"}


@router.get("/{env_id}/credentials", response_model=CredentialsOut)
def credentials(env_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    env = owned_environment(db, user, env_id)
    if env.status != EnvironmentStatus.running:
        raise HTTPException(status_code=409, detail="Credentials are available when the environment is running")
    try:
        values = KubernetesPlatform().get_credentials(env)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Credentials are temporarily unavailable: {exc}") from None
    return CredentialsOut(values=values)


@router.get("/{env_id}/logs", response_model=LogsOut)
def logs(env_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    env = owned_environment(db, user, env_id)
    try:
        return LogsOut(logs=KubernetesPlatform().get_logs(env))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Logs are temporarily unavailable: {exc}") from None
