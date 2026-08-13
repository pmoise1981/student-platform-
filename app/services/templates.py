from sqlalchemy.orm import Session

from app.models import EnvironmentTemplate

TEMPLATES = [
    {
        "id": "backend",
        "name": "Backend",
        "description": "FastAPI + PostgreSQL + Redis",
    },
    {
        "id": "data",
        "name": "Data",
        "description": "Jupyter + Apache Spark + MinIO",
    },
]


def seed_templates(db: Session) -> None:
    for item in TEMPLATES:
        if not db.get(EnvironmentTemplate, item["id"]):
            db.add(EnvironmentTemplate(**item))
    db.commit()
