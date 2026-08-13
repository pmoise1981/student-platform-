from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Environment, EnvironmentStatus, JobAction
from app.services.environments import enqueue_action


def expire_once() -> int:
    """Enqueue deletion for expired environments. Run periodically from cron/systemd later."""
    with SessionLocal() as db:
        envs = db.scalars(
            select(Environment).where(
                Environment.expires_at <= datetime.now(timezone.utc),
                Environment.status.not_in([EnvironmentStatus.deleting, EnvironmentStatus.deleted]),
            )
        ).all()
        for env in envs:
            enqueue_action(db, env, JobAction.delete)
        return len(envs)


if __name__ == "__main__":
    print(f"Enqueued {expire_once()} expired environment(s)")
