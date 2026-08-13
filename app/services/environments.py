from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Environment,
    EnvironmentStatus,
    EnvironmentTemplate,
    JobAction,
    JobStatus,
    ProvisioningJob,
    ResourceAllocation,
    User,
)
from app.schemas.core import EnvironmentCreate

ACTIVE = {
    EnvironmentStatus.requested,
    EnvironmentStatus.provisioning,
    EnvironmentStatus.running,
    EnvironmentStatus.stopping,
    EnvironmentStatus.stopped,
}


def create_environment(db: Session, user: User, payload: EnvironmentCreate, request_key: str | None):
    settings = get_settings()
    if request_key:
        existing = db.scalar(
            select(Environment).where(Environment.user_id == user.id, Environment.request_key == request_key)
        )
        if existing:
            return existing, False

    template = db.get(EnvironmentTemplate, payload.template_id)
    if not template or not template.enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    active_count = db.scalar(
        select(func.count(Environment.id)).where(
            Environment.user_id == user.id,
            Environment.status.in_(ACTIVE),
        )
    )
    if active_count >= settings.max_active_environments_per_user:
        raise HTTPException(status_code=409, detail="Active environment limit reached")

    env_id = __import__("uuid").uuid4()
    short = str(env_id).split("-")[0]
    namespace = f"student-{user.id[:8]}-{short}".lower()
    ttl = payload.ttl_hours or settings.default_ttl_hours
    env = Environment(
        id=str(env_id),
        user_id=user.id,
        template_id=template.id,
        name=payload.name or f"{template.id}-{short}",
        namespace=namespace,
        request_key=request_key,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl),
    )
    env.allocation = ResourceAllocation()
    db.add(env)
    db.flush()
    db.add(ProvisioningJob(environment_id=env.id, action=JobAction.provision, status=JobStatus.queued))
    db.commit()
    db.refresh(env)
    return env, True


def enqueue_action(db: Session, env: Environment, action: JobAction):
    latest_generation = db.scalar(
        select(func.max(ProvisioningJob.generation)).where(
            ProvisioningJob.environment_id == env.id, ProvisioningJob.action == action
        )
    ) or 0
    pending = db.scalar(
        select(ProvisioningJob).where(
            ProvisioningJob.environment_id == env.id,
            ProvisioningJob.action == action,
            ProvisioningJob.status.in_([JobStatus.queued, JobStatus.running]),
        )
    )
    if pending:
        return pending
    job = ProvisioningJob(environment_id=env.id, action=action, generation=latest_generation + 1)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
