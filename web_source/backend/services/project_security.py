"""Authentication, CSRF and RBAC helpers for the project portal."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from typing import Iterable

from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from models.project_models import ProjectAuditEvent, ProjectMember, ProjectRoleRule, ProjectSession


SESSION_COOKIE = "lungtic_project_session"
CSRF_COOKIE = "lungtic_project_csrf"
SESSION_DAYS = 7

ROLES = ("project_admin", "project_lead", "team_lead", "contributor", "observer", "unassigned")
ROLE_RANK = {role: rank for rank, role in enumerate(reversed(ROLES))}


def utcnow() -> datetime:
    return datetime.utcnow()


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def effective_role(member: ProjectMember) -> str:
    return member.manual_role or member.mapped_role or "unassigned"


def role_at_least(member: ProjectMember, role: str) -> bool:
    return ROLE_RANK.get(effective_role(member), -1) >= ROLE_RANK.get(role, 99)


def map_member_role(db: Session, department_ids: Iterable[str], job_title_id: str | None, job_title_name: str | None) -> str:
    departments = {str(value) for value in department_ids}
    normalized_title = (job_title_name or "").strip().casefold()
    rules = db.query(ProjectRoleRule).filter(ProjectRoleRule.active.is_(True)).order_by(
        ProjectRoleRule.priority.desc(), ProjectRoleRule.id.asc()
    ).all()
    for rule in rules:
        if rule.department_id and rule.department_id not in departments:
            continue
        if rule.job_title_id and rule.job_title_id != job_title_id:
            continue
        if rule.job_title_name and rule.job_title_name.strip().casefold() != normalized_title:
            continue
        return rule.role
    return "unassigned"


def create_session(db: Session, member: ProjectMember) -> tuple[str, str, ProjectSession]:
    raw_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    now = utcnow()
    session = ProjectSession(
        token_hash=token_hash(raw_token),
        csrf_hash=token_hash(csrf_token),
        member_id=member.id,
        expires_at=now + timedelta(days=SESSION_DAYS),
        created_at=now,
        last_seen_at=now,
    )
    db.add(session)
    db.flush()
    return raw_token, csrf_token, session


def get_project_session(
    raw_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> ProjectSession:
    if not raw_token:
        raise HTTPException(status_code=401, detail="请使用飞书登录")
    session = db.query(ProjectSession).filter(ProjectSession.token_hash == token_hash(raw_token)).first()
    if not session or session.expires_at <= utcnow():
        if session:
            db.delete(session)
            db.commit()
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    session.last_seen_at = utcnow()
    return session


def get_project_member(
    session: ProjectSession = Depends(get_project_session),
    db: Session = Depends(get_db),
) -> ProjectMember:
    member = db.query(ProjectMember).filter(ProjectMember.id == session.member_id).first()
    if not member or not member.active:
        raise HTTPException(status_code=403, detail="项目成员账号已停用")
    if effective_role(member) == "unassigned":
        raise HTTPException(status_code=403, detail="当前飞书部门或职位尚未映射项目权限")
    return member


def require_role(minimum: str):
    def dependency(member: ProjectMember = Depends(get_project_member)) -> ProjectMember:
        if not role_at_least(member, minimum):
            raise HTTPException(status_code=403, detail="项目权限不足")
        return member
    return dependency


def require_csrf(
    request: Request,
    session: ProjectSession = Depends(get_project_session),
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: str | None = Header(default=None, alias="X-Project-CSRF"),
) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status_code=403, detail="CSRF 校验失败")
    if not hmac.compare_digest(session.csrf_hash, token_hash(csrf_header)):
        raise HTTPException(status_code=403, detail="CSRF 校验失败")


def audit_project(
    db: Session,
    actor: ProjectMember | None,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    detail: dict | None = None,
) -> None:
    db.add(ProjectAuditEvent(
        actor_member_id=actor.id if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail_json=json.dumps(detail or {}, ensure_ascii=False, separators=(",", ":")),
        created_at=utcnow(),
    ))
