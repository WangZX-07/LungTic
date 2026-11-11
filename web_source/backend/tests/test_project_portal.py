"""Security and workflow tests for the isolated project progress portal."""

import hashlib
import hmac
import json
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from models.project_models import ProjectGithubEvent, ProjectMember, ProjectRoleRule, ProjectTask
from routers import project
from services.project_security import CSRF_COOKIE, SESSION_COOKIE, create_session, map_member_role


@pytest.fixture
def portal(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(project.router)

    def override_db():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    now = datetime.utcnow()
    credentials = {}
    with Session() as db:
        members = [
            ProjectMember(
                feishu_open_id=f"ou_{name}", name=name, mapped_role=role,
                department_ids_json="[]", department_names_json="[]",
                active=True, created_at=now, updated_at=now,
            )
            for name, role in [
                ("admin", "project_admin"), ("member", "contributor"), ("observer", "observer"),
            ]
        ]
        db.add_all(members)
        db.flush()
        for member in members:
            raw, csrf, _ = create_session(db, member)
            credentials[member.name] = (raw, csrf, member.id)
        db.commit()

    monkeypatch.setattr(project, "GITHUB_WEBHOOK_SECRET", "synthetic-webhook-secret")
    monkeypatch.setattr(project, "GITHUB_REPOSITORY", "WangZX-07/LungTic")
    with TestClient(app) as client:
        yield client, Session, credentials
    app.dependency_overrides.clear()
    engine.dispose()


def request_as(client, credentials, name, method, path, **kwargs):
    raw, csrf, _ = credentials[name]
    headers = dict(kwargs.pop("headers", {}))
    if method.lower() not in {"get", "head"}:
        headers["X-Project-CSRF"] = csrf
    return client.request(
        method, path, headers=headers,
        cookies={SESSION_COOKIE: raw, CSRF_COOKIE: csrf}, **kwargs,
    )


def test_department_and_title_rules_use_priority(portal):
    _, Session, _ = portal
    now = datetime.utcnow()
    with Session() as db:
        db.add_all([
            ProjectRoleRule(
                name="department contributor", department_id="od-rd", role="contributor",
                priority=10, active=True, created_at=now, updated_at=now,
            ),
            ProjectRoleRule(
                name="department lead", department_id="od-rd", job_title_name="技术负责人",
                role="team_lead", priority=50, active=True, created_at=now, updated_at=now,
            ),
        ])
        db.commit()
        assert map_member_role(db, ["od-rd"], None, "工程师") == "contributor"
        assert map_member_role(db, ["od-rd"], None, "技术负责人") == "team_lead"
        assert map_member_role(db, ["od-other"], None, "技术负责人") == "unassigned"


def test_project_sessions_csrf_and_task_scope(portal):
    client, _, credentials = portal
    assert client.get("/api/project/dashboard").status_code == 401
    raw, _, _ = credentials["admin"]
    assert client.post(
        "/api/project/milestones",
        cookies={SESSION_COOKIE: raw},
        json={"title": "MVP"},
    ).status_code == 403

    milestone = request_as(
        client, credentials, "admin", "post", "/api/project/milestones", json={"title": "MVP"}
    )
    assert milestone.status_code == 200, milestone.text
    member_id = credentials["member"][2]
    task = request_as(
        client, credentials, "admin", "post", "/api/project/tasks",
        json={"title": "Connect Feishu", "milestone_id": milestone.json()["id"], "assignee_member_id": member_id},
    )
    assert task.status_code == 200, task.text
    task_id = task.json()["id"]

    forbidden = request_as(
        client, credentials, "member", "patch", f"/api/project/tasks/{task_id}", json={"title": "Changed"}
    )
    assert forbidden.status_code == 403
    allowed = request_as(
        client, credentials, "member", "patch", f"/api/project/tasks/{task_id}",
        json={"status": "in_progress", "progress": 35},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["progress"] == 35
    assert request_as(
        client, credentials, "observer", "post", "/api/project/progress",
        json={"task_id": task_id, "progress": 40, "completed": "Should not write"},
    ).status_code == 403
    assert request_as(
        client, credentials, "observer", "post", "/api/project/decisions",
        json={"title": "Unauthorized decision", "decision": "Should not write"},
    ).status_code == 403
    decision = request_as(
        client, credentials, "admin", "post", "/api/project/decisions",
        json={"title": "Adopt webhook evidence", "decision": "Use signed GitHub webhooks"},
    )
    assert decision.status_code == 200, decision.text
    update = request_as(
        client, credentials, "member", "post", "/api/project/progress",
        json={"task_id": task_id, "progress": 60, "completed": "Implemented synthetic flow"},
    )
    assert update.status_code == 200, update.text
    assert request_as(
        client, credentials, "member", "post", "/api/project/progress",
        json={"task_id": task_id, "completed": "Unsafe link", "evidence_url": "javascript:alert(1)"},
    ).status_code == 422
    admin_id = credentials["admin"][2]
    assert request_as(
        client, credentials, "admin", "patch", f"/api/project/admin/members/{admin_id}",
        json={"manual_role": "observer"},
    ).status_code == 400


def test_signed_github_webhook_is_deduplicated_and_completes_linked_task(portal):
    client, Session, credentials = portal
    task = request_as(
        client, credentials, "admin", "post", "/api/project/tasks",
        json={"title": "Merge integration", "github_pr_number": 42},
    )
    assert task.status_code == 200, task.text
    payload = {
        "action": "closed",
        "number": 42,
        "repository": {"full_name": "WangZX-07/LungTic"},
        "sender": {"login": "synthetic-dev"},
        "pull_request": {
            "title": "Finish integration", "html_url": "https://github.com/WangZX-07/LungTic/pull/42",
            "updated_at": "2026-11-10T08:00:00Z", "merged": True,
        },
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(b"synthetic-webhook-secret", body, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json", "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "delivery-1", "X-Hub-Signature-256": signature,
    }
    response = client.post("/api/project/integrations/github/webhook", content=body, headers=headers)
    assert response.status_code == 202, response.text
    duplicate = client.post("/api/project/integrations/github/webhook", content=body, headers=headers)
    assert duplicate.status_code == 202
    assert duplicate.json()["status"] == "duplicate"
    bad_headers = {**headers, "X-GitHub-Delivery": "delivery-2", "X-Hub-Signature-256": "sha256=bad"}
    assert client.post("/api/project/integrations/github/webhook", content=body, headers=bad_headers).status_code == 401
    with Session() as db:
        stored = db.query(ProjectTask).filter(ProjectTask.id == task.json()["id"]).one()
        assert stored.status == "done"
        assert stored.progress == 100
        assert db.query(ProjectGithubEvent).count() == 1
