import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EnvironmentStatus(str, enum.Enum):
    requested = "requested"
    provisioning = "provisioning"
    running = "running"
    failed = "failed"
    stopping = "stopping"
    stopped = "stopped"
    deleting = "deleting"
    deleted = "deleted"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class JobAction(str, enum.Enum):
    provision = "provision"
    start = "start"
    stop = "stop"
    delete = "delete"


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    environments = relationship("Environment", back_populates="user")


class EnvironmentTemplate(Base):
    __tablename__ = "environment_templates"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(300))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Environment(Base):
    __tablename__ = "environments"
    __table_args__ = (UniqueConstraint("user_id", "request_key", name="uq_user_request_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("environment_templates.id"))
    name: Mapped[str] = mapped_column(String(100))
    namespace: Mapped[str] = mapped_column(String(63), unique=True)
    status: Mapped[EnvironmentStatus] = mapped_column(Enum(EnvironmentStatus), default=EnvironmentStatus.requested)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="environments")
    deployments = relationship("Deployment", cascade="all, delete-orphan")
    jobs = relationship("ProvisioningJob", cascade="all, delete-orphan")
    allocation = relationship("ResourceAllocation", uselist=False, cascade="all, delete-orphan")


class Deployment(Base):
    __tablename__ = "deployments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"), index=True)
    component: Mapped[str] = mapped_column(String(80))
    desired_replicas: Mapped[int] = mapped_column(Integer, default=1)
    healthy: Mapped[bool] = mapped_column(Boolean, default=False)
    last_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ProvisioningJob(Base):
    __tablename__ = "provisioning_jobs"
    __table_args__ = (UniqueConstraint("environment_id", "action", "generation", name="uq_env_action_generation"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"), index=True)
    action: Mapped[JobAction] = mapped_column(Enum(JobAction))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.queued, index=True)
    generation: Mapped[int] = mapped_column(Integer, default=1)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResourceAllocation(Base):
    __tablename__ = "resource_allocations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"), unique=True)
    cpu_limit: Mapped[str] = mapped_column(String(20), default="2")
    memory_limit: Mapped[str] = mapped_column(String(20), default="3Gi")
    storage_limit: Mapped[str] = mapped_column(String(20), default="5Gi")
    max_pods: Mapped[int] = mapped_column(Integer, default=8)
