import os
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth import TokenVerifier
from app.config import Settings
from app.main import create_app


@pytest.fixture(scope="session")
def settings():
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url or not url.rsplit("/", 1)[-1].endswith("_test"):
        raise RuntimeError("Set TEST_DATABASE_URL to an already-migrated dedicated PostgreSQL *_test database")
    return replace(Settings(), database_url=url, environment="development", dev_auth=True, dev_secret="test-only-secret-" * 4,
                   dev_emails=("owner@example.test", "other@example.test", "worker@example.test"))


@pytest.fixture(scope="session")
def app(settings):
    app = create_app(settings)
    yield app
    app.state.factory.kw["bind"].dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def headers(settings):
    verifier = TokenVerifier(settings)
    return {name: {"Authorization": "Bearer " + verifier.development_token(email)} for name, email in
            {"owner": "owner@example.test", "other": "other@example.test", "worker": "worker@example.test"}.items()}


@pytest.fixture
def company(client, headers):
    def create(actor="owner"):
        response = client.post("/api/v1/organizations", headers=headers[actor], json={"name": "Test Company " + uuid4().hex[:8]})
        assert response.status_code == 201, response.text
        return response.json()["id"]
    return create


@pytest.fixture
def project(client, headers):
    def create(org, actor="owner"):
        response = client.post(f"/api/v1/organizations/{org}/projects", headers=headers[actor], json={"name": "Foundation Works", "code": "P-"+uuid4().hex[:8], "start_date": "2027-01-04", "discipline": "Civil"})
        assert response.status_code == 201, response.text
        return response.json()
    return create


@pytest.fixture
def enroll(client, headers):
    def add(org, actor="worker", role="member"):
        email = {"worker": "worker@example.test", "other": "other@example.test"}[actor]
        response = client.post(f"/api/v1/organizations/{org}/invitations", headers=headers["owner"], json={"email": email, "role": role})
        assert response.status_code == 201, response.text
        token = response.json()["token"]
        response = client.post("/api/v1/invitations/accept", headers=headers[actor], json={"token": token})
        assert response.status_code == 200, response.text
        who = client.get("/api/v1/me", headers=headers[actor]).json()
        return who, token
    return add


@pytest.fixture
def calendar():
    return {"name": "Five day week", "timezone": "Pacific/Port_Moresby", "nominal_minutes_per_day": 480,
            "week": {str(i): [["08:00", "12:00"], ["13:00", "17:00"]] if i < 6 else [] for i in range(1,8)},
            "exceptions": {"2027-01-01": []}}

