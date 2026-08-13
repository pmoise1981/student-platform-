import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import JobStatus, ProvisioningJob
from app.provisioning.orchestrator import Orchestrator

log = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc)


def reclaim_stale_jobs(db):
    cutoff = utcnow() - timedelta(seconds=get_settings().job_stale_seconds)
    stale = db.scalars(
        select(ProvisioningJob).where(
            ProvisioningJob.status == JobStatus.running,
            ProvisioningJob.started_at < cutoff,
        )
    ).all()
    for job in stale:
        job.status = JobStatus.queued
        job.last_error = "Recovered after worker interruption"
    if stale:
        db.commit()


def claim_job(db):
    # PostgreSQL SKIP LOCKED permits more workers later without changing the queue model.
    stmt = (
        select(ProvisioningJob)
        .where(ProvisioningJob.status == JobStatus.queued)
        .order_by(ProvisioningJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = db.scalar(stmt)
    if not job:
        return None
    job.status = JobStatus.running
    job.attempts += 1
    job.started_at = utcnow()
    db.commit()
    db.refresh(job)
    return job


def run_forever():
    settings = get_settings()
    orchestrator = Orchestrator()
    log.info("worker_started")
    while True:
        with SessionLocal() as db:
            reclaim_stale_jobs(db)
            job = claim_job(db)
            if not job:
                time.sleep(settings.job_poll_seconds)
                continue
            try:
                orchestrator.execute(db, job)
                job.status = JobStatus.succeeded
                job.finished_at = utcnow()
                db.commit()
            except Exception as exc:
                job.last_error = str(exc)
                job.finished_at = utcnow()
                if job.attempts < settings.job_max_attempts:
                    job.status = JobStatus.queued
                    log.warning("job_retry", extra={"job_id": job.id, "attempts": job.attempts})
                else:
                    job.status = JobStatus.failed
                db.commit()
                time.sleep(min(2 ** job.attempts, 10))


if __name__ == "__main__":
    run_forever()
