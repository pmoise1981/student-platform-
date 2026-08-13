import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kubernetes.client import KubernetesPlatform
from app.models import Deployment, Environment, EnvironmentStatus, JobAction, ProvisioningJob
from app.observability.metrics import PROVISIONING_DURATION, PROVISIONING_RESULTS, RUNNING_ENVIRONMENTS

log = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc)


class Orchestrator:
    """Coordinates lifecycle steps while the Kubernetes adapter owns primitives.

    Keeping orchestration separate from resource construction makes failures and state
    transitions easy to reason about when studying or testing the project.
    """

    def __init__(self, platform: KubernetesPlatform | None = None):
        self.platform = platform or KubernetesPlatform()

    def execute(self, db: Session, job: ProvisioningJob):
        env = db.get(Environment, job.environment_id)
        if not env:
            raise RuntimeError("Environment no longer exists")
        started = time.perf_counter()
        try:
            if job.action == JobAction.provision:
                self._provision(db, env)
            elif job.action == JobAction.stop:
                self._stop(db, env)
            elif job.action == JobAction.start:
                self._start(db, env)
            elif job.action == JobAction.delete:
                self._delete(db, env)
            PROVISIONING_RESULTS.labels(action=job.action.value, result="success").inc()
        except Exception as exc:
            PROVISIONING_RESULTS.labels(action=job.action.value, result="failure").inc()
            env.status = EnvironmentStatus.failed
            env.error_message = str(exc)
            db.commit()
            log.exception("provisioning_failed", extra={"environment_id": env.id, "job_id": job.id, "action": job.action.value})
            raise
        finally:
            PROVISIONING_DURATION.labels(action=job.action.value).observe(time.perf_counter() - started)

    def _record_components(self, db: Session, env: Environment, health):
        known = {d.component: d for d in env.deployments}
        for item in health:
            dep = known.get(item.name) or Deployment(environment_id=env.id, component=item.name)
            dep.healthy = item.healthy
            dep.last_message = item.message
            db.add(dep)
        db.commit()

    def _provision(self, db: Session, env: Environment):
        # Every step is idempotent. A retry may safely continue after a partial attempt.
        env.status = EnvironmentStatus.provisioning
        env.error_message = None
        db.commit()
        self.platform.ensure_namespace(env)
        self.platform.ensure_controls(env)
        self.platform.ensure_secret(env)
        self.platform.ensure_workloads(env)
        env.url = self.platform.ensure_ingress(env)
        db.commit()
        health = self.platform.wait_ready(env)
        self._record_components(db, env, health)
        env.status = EnvironmentStatus.running
        db.commit()
        RUNNING_ENVIRONMENTS.inc()

    def _stop(self, db: Session, env: Environment):
        if env.status == EnvironmentStatus.stopped:
            return
        env.status = EnvironmentStatus.stopping
        db.commit()
        self.platform.scale(env, 0)
        env.status = EnvironmentStatus.stopped
        db.commit()
        RUNNING_ENVIRONMENTS.dec()

    def _start(self, db: Session, env: Environment):
        if env.status == EnvironmentStatus.running:
            return
        env.status = EnvironmentStatus.provisioning
        db.commit()
        self.platform.scale(env, 1)
        health = self.platform.wait_ready(env)
        self._record_components(db, env, health)
        env.status = EnvironmentStatus.running
        env.error_message = None
        db.commit()
        RUNNING_ENVIRONMENTS.inc()

    def _delete(self, db: Session, env: Environment):
        if env.status == EnvironmentStatus.deleted:
            return
        env.status = EnvironmentStatus.deleting
        db.commit()
        self.platform.delete(env)
        env.status = EnvironmentStatus.deleted
        env.url = None
        db.commit()
