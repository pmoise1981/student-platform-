from types import SimpleNamespace
from sqlalchemy import select

from app.models import EnvironmentStatus, JobAction, ProvisioningJob, User
from app.provisioning.orchestrator import Orchestrator
from app.services.environments import create_environment
from app.schemas.core import EnvironmentCreate


class FakePlatform:
    def ensure_namespace(self,e): pass
    def ensure_controls(self,e): pass
    def ensure_secret(self,e): return {}
    def ensure_workloads(self,e): pass
    def ensure_ingress(self,e): return 'http://backend.localhost:8081'
    def wait_ready(self,e): return [SimpleNamespace(name='fastapi',healthy=True,message='Healthy')]
    def scale(self,e,n): pass
    def delete(self,e): pass


class BrokenPlatform(FakePlatform):
    def ensure_workloads(self,e):
        raise RuntimeError('image pull failed')


def _make(db):
    user = User(email='unit@example.edu', password_hash='x')
    db.add(user)
    db.commit()
    db.refresh(user)
    env, _ = create_environment(db,user,EnvironmentCreate(template_id='backend'),None)
    job = db.scalar(select(ProvisioningJob).where(ProvisioningJob.environment_id==env.id))
    return env, job


def test_provisioning_state_transition(db):
    env, job = _make(db)
    Orchestrator(FakePlatform()).execute(db,job)
    db.refresh(env)
    assert env.status == EnvironmentStatus.running
    assert env.url


def test_failed_provisioning_is_persisted(db):
    env, job = _make(db)
    try:
        Orchestrator(BrokenPlatform()).execute(db,job)
    except RuntimeError:
        pass
    db.refresh(env)
    assert env.status == EnvironmentStatus.failed
    assert 'image pull failed' in env.error_message


def test_stop_is_idempotent(db):
    env, job = _make(db)
    orch = Orchestrator(FakePlatform())
    orch.execute(db,job)
    env.status = EnvironmentStatus.stopped
    db.commit()
    stop_job = ProvisioningJob(environment_id=env.id, action=JobAction.stop, generation=1)
    db.add(stop_job)
    db.commit()
    orch.execute(db,stop_job)
    assert env.status == EnvironmentStatus.stopped
