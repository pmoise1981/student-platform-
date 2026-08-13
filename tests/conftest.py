import os
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.services.templates import seed_templates

engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestingSession() as db:
        seed_templates(db)
    yield

@pytest.fixture
def db():
    with TestingSession() as session:
        yield session

@pytest.fixture
def client():
    def override():
        with TestingSession() as db:
            yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def token(client):
    r = client.post('/api/auth/register', json={'email':'student@example.edu','password':'long-test-password'})
    return r.json()['access_token']

@pytest.fixture
def auth(token):
    return {'Authorization': f'Bearer {token}'}
