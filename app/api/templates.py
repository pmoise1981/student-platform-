from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import get_current_user
from app.db import get_db
from app.models import EnvironmentTemplate, User
from app.schemas.core import TemplateOut

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(EnvironmentTemplate).where(EnvironmentTemplate.enabled.is_(True))).all()


@router.get("/{template_id}", response_model=TemplateOut)
def get_template(template_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    item = db.get(EnvironmentTemplate, template_id)
    if not item or not item.enabled:
        raise HTTPException(status_code=404, detail="Template not found")
    return item
