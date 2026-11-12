"""Single-project progress portal with Feishu identity and GitHub evidence."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from config import (
    FEISHU_APP_ID,
    GITHUB_API_TOKEN,
    GITHUB_REPOSITORY,
    GITHUB_WEBHOOK_SECRET,
    PROJECT_BOOTSTRAP_OPEN_IDS,
    PROJECT_COOKIE_SECURE,
    PROJECT_ORIGIN,
)
from database import get_db
from models.project_models import (
    ProjectGithubEvent,
    ProjectDecision,
    ProjectMember,
    ProjectMilestone,
    ProjectProgressUpdate,
    ProjectRisk,
    ProjectRoleRule,
    ProjectSession,
    ProjectTask,
)
from services.feishu_service import FeishuError, FeishuIdentity, browser_login_url, configured as feishu_configured, exchange_code
from services.github_service import GithubHistoryError, fetch_github_history
from services.project_security import (
    CSRF_COOKIE,
    ROLES,
    SESSION_COOKIE,
    SESSION_DAYS,
    audit_project,
    create_session,
    effective_role,
    get_project_member,
    get_project_session,
    json_list,
    map_member_role,
    require_csrf,
    require_role,
    role_at_least,
    token_hash,
    utcnow,
)


router = APIRouter(prefix="/api/project", tags=["project"])
MILESTONE_STATUSES = {"planned", "active", "completed", "paused"}
TASK_STATUSES = {"todo", "in_progress", "blocked", "review", "done"}
PRIORITIES = {"low", "medium", "high", "urgent"}
RISK_SEVERITIES = {"low", "medium", "high", "critical"}
RISK_STATUSES = {"open", "mitigating", "resolved", "accepted"}
DECISION_STATUSES = {"active", "superseded"}


class FeishuCodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=2048)


class MilestoneInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    status: str = "planned"
    weight: float = Field(default=1.0, gt=0, le=1000)
    start_date: date | None = None
    due_date: date | None = None
    sort_order: int = Field(default=0, ge=-100000, le=100000)


class MilestonePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    status: str | None = None
    weight: float | None = Field(default=None, gt=0, le=1000)
    start_date: date | None = None
    due_date: date | None = None
    sort_order: int | None = Field(default=None, ge=-100000, le=100000)


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=20000)
    milestone_id: int | None = None
    status: str = "todo"
    priority: str = "medium"
    assignee_member_id: int | None = None
    due_date: date | None = None
    weight: float = Field(default=1.0, gt=0, le=1000)
    progress: int = Field(default=0, ge=0, le=100)
    github_issue_number: int | None = Field(default=None, gt=0)
    github_pr_number: int | None = Field(default=None, gt=0)
    github_url: str | None = Field(default=None, max_length=512)

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, value: str | None):
        return _safe_external_url(value)


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=20000)
    milestone_id: int | None = None
    status: str | None = None
    priority: str | None = None
    assignee_member_id: int | None = None
    due_date: date | None = None
    weight: float | None = Field(default=None, gt=0, le=1000)
    progress: int | None = Field(default=None, ge=0, le=100)
    github_issue_number: int | None = Field(default=None, gt=0)
    github_pr_number: int | None = Field(default=None, gt=0)
    github_url: str | None = Field(default=None, max_length=512)

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, value: str | None):
        return _safe_external_url(value)


class ProgressInput(BaseModel):
    task_id: int | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    completed: str = Field(min_length=1, max_length=10000)
    next_steps: str | None = Field(default=None, max_length=10000)
    blockers: str | None = Field(default=None, max_length=10000)
    evidence_url: str | None = Field(default=None, max_length=512)

    @field_validator("evidence_url")
    @classmethod
    def validate_evidence_url(cls, value: str | None):
        return _safe_external_url(value)


class RiskInput(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    severity: str = "medium"
    status: str = "open"
    mitigation: str | None = Field(default=None, max_length=10000)
    owner_member_id: int | None = None
    due_date: date | None = None


class RiskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    severity: str | None = None
    status: str | None = None
    mitigation: str | None = Field(default=None, max_length=10000)
    owner_member_id: int | None = None
    due_date: date | None = None


class DecisionInput(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    context: str | None = Field(default=None, max_length=10000)
    decision: str = Field(min_length=1, max_length=10000)
    rationale: str | None = Field(default=None, max_length=10000)
    status: str = "active"
    decided_by_member_id: int | None = None


class RoleRuleInput(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    department_id: str | None = Field(default=None, max_length=128)
    job_title_id: str | None = Field(default=None, max_length=128)
    job_title_name: str | None = Field(default=None, max_length=128)
    role: str
    priority: int = Field(default=100, ge=-100000, le=100000)
    active: bool = True

    @field_validator("department_id", "job_title_id", "job_title_name", mode="before")
    @classmethod
    def normalize_optional_rule_value(cls, value):
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("department_id")
    @classmethod
    def validate_open_department_id(cls, value: str | None):
        if value is not None and not value.startswith("od-"):
            raise ValueError("飞书部门 ID 必须是以 od- 开头的 open_department_id")
        return value

    @field_validator("job_title_id")
    @classmethod
    def reject_department_id_as_job_title(cls, value: str | None):
        if value is not None and value.startswith("od-"):
            raise ValueError("不能把以 od- 开头的部门 ID 填入职位 ID")
        return value

    @model_validator(mode="after")
    def require_mapping_condition(self):
        if not any([self.department_id, self.job_title_id, self.job_title_name]):
            raise ValueError("至少填写部门 ID、职位 ID 或职位名称之一")
        return self


class GithubHistorySyncInput(BaseModel):
    days: int = Field(default=365, ge=1, le=3650)
    import_tasks: bool = True


class MemberAdminPatch(BaseModel):
    manual_role: str | None = None
    github_login: str | None = Field(default=None, max_length=128)
    active: bool | None = None


def _safe_external_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if not (normalized.startswith("https://") or normalized.startswith("http://")):
        raise ValueError("链接必须使用 http:// 或 https://")
    return normalized


def _set_auth_cookies(response: Response, raw_token: str, csrf_token: str) -> None:
    max_age = SESSION_DAYS * 24 * 60 * 60
    response.set_cookie(
        SESSION_COOKIE, raw_token, max_age=max_age, httponly=True,
        secure=PROJECT_COOKIE_SECURE, samesite="lax", path="/",
    )
    response.set_cookie(
        CSRF_COOKIE, csrf_token, max_age=max_age, httponly=False,
        secure=PROJECT_COOKIE_SECURE, samesite="lax", path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def _upsert_identity(db: Session, identity: FeishuIdentity) -> ProjectMember:
    now = utcnow()
    member = db.query(ProjectMember).filter(ProjectMember.feishu_open_id == identity.open_id).first()
    if member is None:
        member = ProjectMember(
            feishu_open_id=identity.open_id,
            name=identity.name,
            created_at=now,
            updated_at=now,
        )
        db.add(member)
        db.flush()
    member.feishu_union_id = identity.union_id
    member.feishu_user_id = identity.user_id
    member.name = identity.name
    member.avatar_url = identity.avatar_url
    member.department_ids_json = json.dumps(identity.department_ids, ensure_ascii=False)
    member.department_names_json = json.dumps(identity.department_names, ensure_ascii=False)
    member.job_title_id = identity.job_title_id
    member.job_title_name = identity.job_title_name
    member.mapped_role = map_member_role(
        db, identity.department_ids, identity.job_title_id, identity.job_title_name
    )
    if identity.open_id in PROJECT_BOOTSTRAP_OPEN_IDS:
        member.manual_role = "project_admin"
    member.last_synced_at = now
    member.updated_at = now
    return member


def _finish_login(db: Session, identity: FeishuIdentity, response: Response) -> ProjectMember:
    member = _upsert_identity(db, identity)
    if not member.active:
        raise HTTPException(status_code=403, detail="项目成员账号已停用")
    if effective_role(member) == "unassigned":
        db.commit()
        raise HTTPException(status_code=403, detail="当前部门或职位尚未配置项目权限")
    db.query(ProjectSession).filter(
        ProjectSession.member_id == member.id,
        ProjectSession.expires_at <= utcnow(),
    ).delete(synchronize_session=False)
    raw_token, csrf_token, _ = create_session(db, member)
    audit_project(db, member, "login", "project_session")
    db.commit()
    _set_auth_cookies(response, raw_token, csrf_token)
    return member


def _member_dict(member: ProjectMember) -> dict:
    return {
        "id": member.id,
        "name": member.name,
        "avatar_url": member.avatar_url,
        "role": effective_role(member),
        "mapped_role": member.mapped_role,
        "manual_role": member.manual_role,
        "department_ids": json_list(member.department_ids_json),
        "department_names": json_list(member.department_names_json),
        "job_title_id": member.job_title_id,
        "job_title_name": member.job_title_name,
        "github_login": member.github_login,
        "active": member.active,
        "last_synced_at": member.last_synced_at,
    }


def _milestone_dict(row: ProjectMilestone, progress: int | None = None) -> dict:
    return {
        "id": row.id, "title": row.title, "description": row.description,
        "status": row.status, "weight": row.weight, "start_date": row.start_date,
        "due_date": row.due_date, "sort_order": row.sort_order,
        "progress": progress, "created_at": row.created_at, "updated_at": row.updated_at,
    }


def _task_dict(row: ProjectTask, names: dict[int, str]) -> dict:
    return {
        "id": row.id, "milestone_id": row.milestone_id, "title": row.title,
        "description": row.description, "status": row.status, "priority": row.priority,
        "assignee_member_id": row.assignee_member_id,
        "assignee_name": names.get(row.assignee_member_id) if row.assignee_member_id else None,
        "due_date": row.due_date, "weight": row.weight, "progress": row.progress,
        "github_issue_number": row.github_issue_number, "github_pr_number": row.github_pr_number,
        "github_url": row.github_url, "created_at": row.created_at, "updated_at": row.updated_at,
    }


def _validate_choice(value: str, allowed: set[str], label: str) -> None:
    if value not in allowed:
        raise HTTPException(status_code=400, detail=f"{label}无效")


def _ensure_member(db: Session, member_id: int | None) -> None:
    if member_id is not None and not db.query(ProjectMember).filter(
        ProjectMember.id == member_id, ProjectMember.active.is_(True)
    ).first():
        raise HTTPException(status_code=400, detail="项目成员不存在或已停用")


@router.get("/auth/config")
def auth_config():
    return {"configured": feishu_configured(), "app_id": FEISHU_APP_ID or None}


@router.get("/auth/start")
def auth_start():
    if not feishu_configured():
        raise HTTPException(status_code=503, detail="服务器尚未配置飞书应用")
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(browser_login_url(state), status_code=302)
    response.set_cookie(
        "lungtic_project_oauth_state", state, max_age=600, httponly=True,
        secure=PROJECT_COOKIE_SECURE, samesite="lax", path="/api/project/auth/callback",
    )
    return response


@router.get("/auth/callback")
def auth_callback(
    code: str = "",
    state: str = "",
    oauth_state: str | None = Cookie(default=None, alias="lungtic_project_oauth_state"),
    db: Session = Depends(get_db),
):
    if not oauth_state or not state or not hmac.compare_digest(oauth_state, state):
        query = urlencode({"error": "登录状态校验失败，请重试"})
        return RedirectResponse(f"{PROJECT_ORIGIN}/#/login?{query}", status_code=302)
    response = RedirectResponse(f"{PROJECT_ORIGIN}/#/auth-complete", status_code=302)
    response.delete_cookie("lungtic_project_oauth_state", path="/api/project/auth/callback")
    try:
        _finish_login(db, exchange_code(code), response)
    except (FeishuError, HTTPException) as exc:
        db.rollback()
        message = exc.detail if isinstance(exc, HTTPException) else str(exc)
        query = urlencode({"error": message})
        return RedirectResponse(f"{PROJECT_ORIGIN}/#/login?{query}", status_code=302)
    return response


@router.post("/auth/feishu-client")
def auth_feishu_client(req: FeishuCodeRequest, response: Response, db: Session = Depends(get_db)):
    try:
        member = _finish_login(db, exchange_code(req.code), response)
        return _member_dict(member)
    except FeishuError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/me")
def project_me(member: ProjectMember = Depends(get_project_member)):
    return _member_dict(member)


@router.post("/auth/logout", dependencies=[Depends(require_csrf)])
def project_logout(
    response: Response,
    session: ProjectSession = Depends(get_project_session),
    db: Session = Depends(get_db),
):
    db.delete(session)
    db.commit()
    _clear_auth_cookies(response)
    return {"status": "ok"}


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    member: ProjectMember = Depends(get_project_member),
):
    tasks = db.query(ProjectTask).all()
    total_weight = sum(max(task.weight or 0, 0) for task in tasks)
    weighted = sum(max(task.weight or 0, 0) * (100 if task.status == "done" else task.progress) for task in tasks)
    project_progress = round(weighted / total_weight) if total_weight else None
    today = date.today()
    open_tasks = [task for task in tasks if task.status != "done"]
    milestones = db.query(ProjectMilestone).order_by(ProjectMilestone.sort_order, ProjectMilestone.id).all()
    recent_updates = db.query(ProjectProgressUpdate).order_by(ProjectProgressUpdate.created_at.desc()).limit(8).all()
    member_names = {row.id: row.name for row in db.query(ProjectMember).all()}
    github_evidence_count = db.query(ProjectGithubEvent).count()
    return {
        "project": {
            "name": "LungTic", "progress": project_progress,
            "has_tasks": bool(tasks), "task_count": len(tasks),
            "github_evidence_count": github_evidence_count,
        },
        "metrics": {
            "open_tasks": len(open_tasks),
            "my_open_tasks": sum(1 for task in open_tasks if task.assignee_member_id == member.id),
            "overdue_tasks": sum(1 for task in open_tasks if task.due_date and task.due_date < today),
            "open_risks": db.query(ProjectRisk).filter(ProjectRisk.status.in_(["open", "mitigating"])).count(),
        },
        "milestones": [_milestone_dict(row, _milestone_progress(row.id, tasks)) for row in milestones],
        "recent_updates": [
            {
                "id": row.id, "task_id": row.task_id, "member_id": row.member_id,
                "member_name": member_names.get(row.member_id, "未知成员"), "progress": row.progress,
                "completed": row.completed, "next_steps": row.next_steps, "blockers": row.blockers,
                "evidence_url": row.evidence_url, "created_at": row.created_at,
            } for row in recent_updates
        ],
    }


def _milestone_progress(milestone_id: int, tasks: list[ProjectTask]) -> int:
    scoped = [task for task in tasks if task.milestone_id == milestone_id]
    total = sum(max(task.weight or 0, 0) for task in scoped)
    if not total:
        return 0
    value = sum(max(task.weight or 0, 0) * (100 if task.status == "done" else task.progress) for task in scoped)
    return round(value / total)


@router.get("/milestones")
def list_milestones(db: Session = Depends(get_db), _: ProjectMember = Depends(get_project_member)):
    tasks = db.query(ProjectTask).all()
    rows = db.query(ProjectMilestone).order_by(ProjectMilestone.sort_order, ProjectMilestone.id).all()
    return [_milestone_dict(row, _milestone_progress(row.id, tasks)) for row in rows]


@router.get("/members")
def member_directory(db: Session = Depends(get_db), _: ProjectMember = Depends(get_project_member)):
    """Return the minimum directory data needed for assignment controls."""
    return [
        {"id": row.id, "name": row.name, "role": effective_role(row), "avatar_url": row.avatar_url}
        for row in db.query(ProjectMember).filter(ProjectMember.active.is_(True)).order_by(ProjectMember.name).all()
        if effective_role(row) != "unassigned"
    ]


@router.post("/milestones", dependencies=[Depends(require_csrf)])
def create_milestone(
    req: MilestoneInput,
    db: Session = Depends(get_db),
    member: ProjectMember = Depends(require_role("project_lead")),
):
    _validate_choice(req.status, MILESTONE_STATUSES, "里程碑状态")
    if req.start_date and req.due_date and req.due_date < req.start_date:
        raise HTTPException(status_code=400, detail="截止日期不能早于开始日期")
    now = utcnow()
    row = ProjectMilestone(**req.model_dump(), created_by_member_id=member.id, created_at=now, updated_at=now)
    db.add(row)
    db.flush()
    audit_project(db, member, "create", "milestone", row.id)
    db.commit()
    db.refresh(row)
    return _milestone_dict(row, 0)


@router.patch("/milestones/{milestone_id}", dependencies=[Depends(require_csrf)])
def update_milestone(
    milestone_id: int,
    req: MilestonePatch,
    db: Session = Depends(get_db),
    member: ProjectMember = Depends(require_role("project_lead")),
):
    row = db.query(ProjectMilestone).filter(ProjectMilestone.id == milestone_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="里程碑不存在")
    values = req.model_dump(exclude_unset=True)
    if values.get("status") is not None:
        _validate_choice(values["status"], MILESTONE_STATUSES, "里程碑状态")
    for key, value in values.items():
        setattr(row, key, value)
    if row.start_date and row.due_date and row.due_date < row.start_date:
        raise HTTPException(status_code=400, detail="截止日期不能早于开始日期")
    row.updated_at = utcnow()
    audit_project(db, member, "update", "milestone", row.id, values)
    db.commit()
    return _milestone_dict(row, _milestone_progress(row.id, db.query(ProjectTask).all()))


@router.get("/tasks")
def list_tasks(
    mine: bool = False,
    status: str | None = None,
    db: Session = Depends(get_db),
    member: ProjectMember = Depends(get_project_member),
):
    query = db.query(ProjectTask)
    if mine:
        query = query.filter(ProjectTask.assignee_member_id == member.id)
    if status:
        _validate_choice(status, TASK_STATUSES, "任务状态")
        query = query.filter(ProjectTask.status == status)
    rows = query.order_by(ProjectTask.due_date.asc(), ProjectTask.id.desc()).all()
    names = {row.id: row.name for row in db.query(ProjectMember).all()}
    return [_task_dict(row, names) for row in rows]


@router.post("/tasks", dependencies=[Depends(require_csrf)])
def create_task(
    req: TaskInput,
    db: Session = Depends(get_db),
    member: ProjectMember = Depends(require_role("team_lead")),
):
    _validate_choice(req.status, TASK_STATUSES, "任务状态")
    _validate_choice(req.priority, PRIORITIES, "任务优先级")
    _ensure_member(db, req.assignee_member_id)
    if req.milestone_id and not db.query(ProjectMilestone).filter(ProjectMilestone.id == req.milestone_id).first():
        raise HTTPException(status_code=400, detail="里程碑不存在")
    now = utcnow()
    values = req.model_dump()
    if values["status"] == "done":
        values["progress"] = 100
    row = ProjectTask(**values, created_by_member_id=member.id, created_at=now, updated_at=now)
    db.add(row)
    try:
        db.flush()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="关联的 GitHub Issue 或 PR 已被其他任务占用") from exc
    audit_project(db, member, "create", "task", row.id)
    db.commit()
    db.refresh(row)
    names = {entry.id: entry.name for entry in db.query(ProjectMember).all()}
    return _task_dict(row, names)


@router.patch("/tasks/{task_id}", dependencies=[Depends(require_csrf)])
def update_task(
    task_id: int,
    req: TaskPatch,
    db: Session = Depends(get_db),
    member: ProjectMember = Depends(get_project_member),
):
    row = db.query(ProjectTask).filter(ProjectTask.id == task_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    values = req.model_dump(exclude_unset=True)
    lead = role_at_least(member, "team_lead")
    if not lead:
        if row.assignee_member_id != member.id:
            raise HTTPException(status_code=403, detail="只能更新分配给自己的任务")
        allowed = {"status", "progress"}
        if set(values) - allowed:
            raise HTTPException(status_code=403, detail="成员只能更新任务状态和进度")
    if values.get("status") is not None:
        _validate_choice(values["status"], TASK_STATUSES, "任务状态")
    if values.get("priority") is not None:
        _validate_choice(values["priority"], PRIORITIES, "任务优先级")
    if "assignee_member_id" in values:
        _ensure_member(db, values["assignee_member_id"])
    if values.get("milestone_id") and not db.query(ProjectMilestone).filter(ProjectMilestone.id == values["milestone_id"]).first():
        raise HTTPException(status_code=400, detail="里程碑不存在")
    for key, value in values.items():
        setattr(row, key, value)
    if row.status == "done":
        row.progress = 100
    elif row.progress == 100:
        row.status = "done"
    row.updated_at = utcnow()
    audit_project(db, member, "update", "task", row.id, values)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="关联的 GitHub Issue 或 PR 已被其他任务占用") from exc
    names = {entry.id: entry.name for entry in db.query(ProjectMember).all()}
    return _task_dict(row, names)


@router.get("/progress")
def list_progress(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: ProjectMember = Depends(get_project_member),
):
    limit = max(1, min(limit, 100))
    rows = db.query(ProjectProgressUpdate).order_by(ProjectProgressUpdate.created_at.desc()).limit(limit).all()
    names = {row.id: row.name for row in db.query(ProjectMember).all()}
    tasks = {row.id: row.title for row in db.query(ProjectTask).all()}
    return [
        {
            "id": row.id, "task_id": row.task_id, "task_title": tasks.get(row.task_id),
            "member_id": row.member_id, "member_name": names.get(row.member_id, "未知成员"),
            "progress": row.progress, "completed": row.completed, "next_steps": row.next_steps,
            "blockers": row.blockers, "evidence_url": row.evidence_url, "created_at": row.created_at,
        } for row in rows
    ]


@router.post("/progress", dependencies=[Depends(require_csrf)])
def create_progress(
    req: ProgressInput,
    db: Session = Depends(get_db),
    member: ProjectMember = Depends(require_role("contributor")),
):
    task = None
    if req.task_id is not None:
        task = db.query(ProjectTask).filter(ProjectTask.id == req.task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if not role_at_least(member, "team_lead") and task.assignee_member_id != member.id:
            raise HTTPException(status_code=403, detail="只能填报分配给自己的任务")
        if req.progress is not None:
            task.progress = req.progress
            task.status = "done" if req.progress == 100 else ("in_progress" if task.status == "todo" else task.status)
            task.updated_at = utcnow()
    row = ProjectProgressUpdate(
        task_id=req.task_id, member_id=member.id, progress=req.progress,
        completed=req.completed.strip(), next_steps=req.next_steps,
        blockers=req.blockers, evidence_url=req.evidence_url, created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    audit_project(db, member, "create", "progress_update", row.id, {"task_id": req.task_id})
    db.commit()
    return {"id": row.id, "created_at": row.created_at}


@router.get("/risks")
def list_risks(db: Session = Depends(get_db), _: ProjectMember = Depends(get_project_member)):
    names = {row.id: row.name for row in db.query(ProjectMember).all()}
    rows = db.query(ProjectRisk).order_by(ProjectRisk.status, ProjectRisk.severity.desc(), ProjectRisk.id.desc()).all()
    return [
        {
            "id": row.id, "title": row.title, "description": row.description,
            "severity": row.severity, "status": row.status, "mitigation": row.mitigation,
            "owner_member_id": row.owner_member_id, "owner_name": names.get(row.owner_member_id),
            "due_date": row.due_date, "created_at": row.created_at, "updated_at": row.updated_at,
        } for row in rows
    ]


@router.post("/risks", dependencies=[Depends(require_csrf)])
def create_risk(
    req: RiskInput,
    db: Session = Depends(get_db),
    member: ProjectMember = Depends(require_role("contributor")),
):
    _validate_choice(req.severity, RISK_SEVERITIES, "风险级别")
    _validate_choice(req.status, RISK_STATUSES, "风险状态")
    _ensure_member(db, req.owner_member_id)
    now = utcnow()
    row = ProjectRisk(**req.model_dump(), created_by_member_id=member.id, created_at=now, updated_at=now)
    db.add(row)
    db.flush()
    audit_project(db, member, "create", "risk", row.id)
    db.commit()
    return {"id": row.id}


@router.patch("/risks/{risk_id}", dependencies=[Depends(require_csrf)])
def update_risk(
    risk_id: int,
    req: RiskPatch,
    db: Session = Depends(get_db),
    member: ProjectMember = Depends(require_role("team_lead")),
):
    row = db.query(ProjectRisk).filter(ProjectRisk.id == risk_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="风险不存在")
    values = req.model_dump(exclude_unset=True)
    if values.get("severity") is not None:
        _validate_choice(values["severity"], RISK_SEVERITIES, "风险级别")
    if values.get("status") is not None:
        _validate_choice(values["status"], RISK_STATUSES, "风险状态")
    if "owner_member_id" in values:
        _ensure_member(db, values["owner_member_id"])
    for key, value in values.items():
        setattr(row, key, value)
    row.updated_at = utcnow()
    audit_project(db, member, "update", "risk", row.id, values)
    db.commit()
    return {"id": row.id, "status": row.status}


@router.get("/decisions")
def list_decisions(db: Session = Depends(get_db), _: ProjectMember = Depends(get_project_member)):
    names = {row.id: row.name for row in db.query(ProjectMember).all()}
    rows = db.query(ProjectDecision).order_by(ProjectDecision.decided_at.desc(), ProjectDecision.id.desc()).all()
    return [
        {
            "id": row.id, "title": row.title, "context": row.context, "decision": row.decision,
            "rationale": row.rationale, "status": row.status,
            "decided_by_member_id": row.decided_by_member_id,
            "decided_by_name": names.get(row.decided_by_member_id), "decided_at": row.decided_at,
        } for row in rows
    ]


@router.post("/decisions", dependencies=[Depends(require_csrf)])
def create_decision(
    req: DecisionInput,
    db: Session = Depends(get_db),
    member: ProjectMember = Depends(require_role("team_lead")),
):
    _validate_choice(req.status, DECISION_STATUSES, "决策状态")
    decided_by = req.decided_by_member_id or member.id
    _ensure_member(db, decided_by)
    now = utcnow()
    row = ProjectDecision(
        **req.model_dump(exclude={"decided_by_member_id"}), decided_by_member_id=decided_by,
        created_by_member_id=member.id, decided_at=now, created_at=now, updated_at=now,
    )
    db.add(row)
    db.flush()
    audit_project(db, member, "create", "decision", row.id)
    db.commit()
    return {"id": row.id}


@router.get("/activity")
def list_activity(
    limit: int = 80,
    db: Session = Depends(get_db),
    _: ProjectMember = Depends(get_project_member),
):
    limit = max(1, min(limit, 200))
    rows = db.query(ProjectGithubEvent).order_by(ProjectGithubEvent.occurred_at.desc()).limit(limit).all()
    return [
        {
            "id": row.id, "event_type": row.event_type, "action": row.action,
            "actor_login": row.actor_login, "member_id": row.member_id,
            "repository": row.repository, "title": row.title, "url": row.url,
            "reference": row.reference, "occurred_at": row.occurred_at,
        } for row in rows
    ]


@router.get("/admin/integrations")
def integration_status(
    db: Session = Depends(get_db),
    _: ProjectMember = Depends(require_role("project_admin")),
):
    last_history = db.query(ProjectGithubEvent).filter(
        ProjectGithubEvent.delivery_id.like("history:%")
    ).order_by(ProjectGithubEvent.received_at.desc()).first()
    return {
        "feishu": {"configured": feishu_configured(), "app_id": FEISHU_APP_ID or None},
        "github": {
            "configured": bool(GITHUB_WEBHOOK_SECRET and GITHUB_REPOSITORY),
            "repository": GITHUB_REPOSITORY,
            "webhook_path": "/api/project/integrations/github/webhook",
            "history_sync_available": bool(GITHUB_REPOSITORY),
            "api_token_configured": bool(GITHUB_API_TOKEN),
            "last_history_sync_at": last_history.received_at if last_history else None,
        },
    }


@router.get("/admin/members")
def list_members(db: Session = Depends(get_db), _: ProjectMember = Depends(require_role("project_admin"))):
    return [_member_dict(row) for row in db.query(ProjectMember).order_by(ProjectMember.name).all()]


@router.patch("/admin/members/{member_id}", dependencies=[Depends(require_csrf)])
def update_member(
    member_id: int,
    req: MemberAdminPatch,
    db: Session = Depends(get_db),
    admin: ProjectMember = Depends(require_role("project_admin")),
):
    row = db.query(ProjectMember).filter(ProjectMember.id == member_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="项目成员不存在")
    values = req.model_dump(exclude_unset=True)
    if "manual_role" in values and values["manual_role"] is not None and values["manual_role"] not in ROLES[:-1]:
        raise HTTPException(status_code=400, detail="项目角色无效")
    if row.id == admin.id:
        proposed_active = values.get("active", row.active)
        proposed_manual_role = values.get("manual_role", row.manual_role)
        proposed_role = proposed_manual_role or row.mapped_role
        if not proposed_active or proposed_role != "project_admin":
            raise HTTPException(status_code=400, detail="不能停用或降级当前管理员账号")
    if "github_login" in values:
        values["github_login"] = (values["github_login"] or "").strip() or None
    for key, value in values.items():
        setattr(row, key, value)
    row.updated_at = utcnow()
    audit_project(db, admin, "update", "project_member", row.id, values)
    db.commit()
    return _member_dict(row)


def _validate_rule(req: RoleRuleInput) -> None:
    if req.role not in ROLES[:-1]:
        raise HTTPException(status_code=400, detail="项目角色无效")
    if not any([req.department_id, req.job_title_id, req.job_title_name]):
        raise HTTPException(status_code=400, detail="至少填写一个飞书部门或职位匹配条件")


def _remap_members(db: Session) -> None:
    for member in db.query(ProjectMember).all():
        member.mapped_role = map_member_role(
            db, json_list(member.department_ids_json), member.job_title_id, member.job_title_name
        )
        member.updated_at = utcnow()


@router.get("/admin/role-rules")
def list_role_rules(db: Session = Depends(get_db), _: ProjectMember = Depends(require_role("project_admin"))):
    rows = db.query(ProjectRoleRule).order_by(ProjectRoleRule.priority.desc(), ProjectRoleRule.id).all()
    return [
        {
            "id": row.id, "name": row.name, "department_id": row.department_id,
            "job_title_id": row.job_title_id, "job_title_name": row.job_title_name,
            "role": row.role, "priority": row.priority, "active": row.active,
        } for row in rows
    ]


@router.post("/admin/role-rules", dependencies=[Depends(require_csrf)])
def create_role_rule(
    req: RoleRuleInput,
    db: Session = Depends(get_db),
    admin: ProjectMember = Depends(require_role("project_admin")),
):
    _validate_rule(req)
    now = utcnow()
    row = ProjectRoleRule(**req.model_dump(), created_at=now, updated_at=now)
    db.add(row)
    db.flush()
    _remap_members(db)
    audit_project(db, admin, "create", "role_rule", row.id)
    db.commit()
    return {"id": row.id}


@router.put("/admin/role-rules/{rule_id}", dependencies=[Depends(require_csrf)])
def update_role_rule(
    rule_id: int,
    req: RoleRuleInput,
    db: Session = Depends(get_db),
    admin: ProjectMember = Depends(require_role("project_admin")),
):
    _validate_rule(req)
    row = db.query(ProjectRoleRule).filter(ProjectRoleRule.id == rule_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="映射规则不存在")
    for key, value in req.model_dump().items():
        setattr(row, key, value)
    row.updated_at = utcnow()
    _remap_members(db)
    audit_project(db, admin, "update", "role_rule", row.id)
    db.commit()
    return {"id": row.id}


@router.delete("/admin/role-rules/{rule_id}", dependencies=[Depends(require_csrf)])
def delete_role_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    admin: ProjectMember = Depends(require_role("project_admin")),
):
    row = db.query(ProjectRoleRule).filter(ProjectRoleRule.id == rule_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="映射规则不存在")
    db.delete(row)
    db.flush()
    _remap_members(db)
    audit_project(db, admin, "delete", "role_rule", rule_id)
    db.commit()
    return {"status": "ok"}


def _parse_github_time(value: str | None) -> datetime:
    if not value:
        return utcnow()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return utcnow()


def _github_summary(event_type: str, payload: dict) -> dict:
    actor = (payload.get("sender") or {}).get("login") or (payload.get("pusher") or {}).get("name")
    action = payload.get("action")
    title = event_type
    url = None
    reference = None
    occurred = None
    number = None
    if event_type == "pull_request":
        item = payload.get("pull_request") or {}
        number = payload.get("number")
        title, url = item.get("title") or "Pull request", item.get("html_url")
        reference, occurred = f"PR #{number}", item.get("updated_at")
    elif event_type == "issues":
        item = payload.get("issue") or {}
        number = item.get("number")
        title, url = item.get("title") or "Issue", item.get("html_url")
        reference, occurred = f"Issue #{number}", item.get("updated_at")
    elif event_type == "push":
        commit = payload.get("head_commit") or {}
        reference = (payload.get("ref") or "").removeprefix("refs/heads/")
        title = (commit.get("message") or f"推送到 {reference}").splitlines()[0][:512]
        url, occurred = payload.get("compare"), commit.get("timestamp")
    elif event_type == "workflow_run":
        item = payload.get("workflow_run") or {}
        title = item.get("name") or "Workflow run"
        url, occurred = item.get("html_url"), item.get("updated_at")
        reference = item.get("conclusion") or item.get("status")
    elif event_type == "release":
        item = payload.get("release") or {}
        title = item.get("name") or item.get("tag_name") or "Release"
        url, occurred = item.get("html_url"), item.get("published_at") or item.get("created_at")
        reference = item.get("tag_name")
    return {
        "actor": actor, "action": action, "title": str(title)[:512], "url": url,
        "reference": reference, "occurred_at": _parse_github_time(occurred), "number": number,
    }


def _history_member_id(members_by_login: dict[str, ProjectMember], logins: list[str | None]) -> int | None:
    for login in logins:
        if login and login.casefold() in members_by_login:
            return members_by_login[login.casefold()].id
    return None


def _sync_history_task(
    db: Session,
    item: dict,
    admin: ProjectMember,
    members_by_login: dict[str, ProjectMember],
    import_tasks: bool,
) -> tuple[bool, bool]:
    """Return (created, completed) for a GitHub issue/PR work item."""
    number = item.get("number")
    event_type = item.get("event_type")
    if not isinstance(number, int) or event_type not in {"issues", "pull_request"}:
        return False, False
    field = ProjectTask.github_issue_number if event_type == "issues" else ProjectTask.github_pr_number
    task = db.query(ProjectTask).filter(field == number).first()
    completed = bool(item.get("complete"))
    if task:
        changed = completed and (task.status != "done" or task.progress != 100)
        if changed:
            task.status, task.progress, task.updated_at = "done", 100, utcnow()
        return False, changed

    # Closed, unmerged pull requests are evidence but not completed work and
    # should not create a misleading task.
    if not import_tasks or (event_type == "pull_request" and item.get("state") == "closed" and not completed):
        return False, False
    assignee_id = _history_member_id(
        members_by_login,
        [*(item.get("assignee_logins") or []), item.get("actor_login")],
    )
    status = "done" if completed else ("review" if event_type == "pull_request" else "todo")
    now = utcnow()
    task = ProjectTask(
        title=str(item.get("title") or "GitHub work item")[:240],
        description=f"从 GitHub 历史同步的 {'Issue' if event_type == 'issues' else 'Pull Request'} #{number}。",
        status=status, priority="medium", assignee_member_id=assignee_id,
        weight=1.0, progress=100 if completed else 0,
        github_issue_number=number if event_type == "issues" else None,
        github_pr_number=number if event_type == "pull_request" else None,
        github_url=item.get("url"), created_by_member_id=admin.id,
        created_at=item.get("created_at") or now, updated_at=now,
    )
    db.add(task)
    return True, completed


@router.post("/admin/github/sync-history", dependencies=[Depends(require_csrf)])
def sync_github_history(
    req: GithubHistorySyncInput,
    db: Session = Depends(get_db),
    admin: ProjectMember = Depends(require_role("project_admin")),
):
    if not GITHUB_REPOSITORY:
        raise HTTPException(status_code=503, detail="GitHub 仓库尚未配置")
    since = utcnow() - timedelta(days=req.days)
    try:
        items = fetch_github_history(GITHUB_REPOSITORY, GITHUB_API_TOKEN, since)
    except GithubHistoryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    members_by_login = {
        row.github_login.casefold(): row
        for row in db.query(ProjectMember).filter(ProjectMember.github_login.isnot(None)).all()
        if row.github_login
    }
    now = utcnow()
    inserted = updated = tasks_created = tasks_completed = 0
    counts: dict[str, int] = {}
    for item in items:
        key = str(item.get("key") or "")
        if not key or key.endswith(":None"):
            continue
        delivery_id = "history:" + key
        row = db.query(ProjectGithubEvent).filter(ProjectGithubEvent.delivery_id == delivery_id).first()
        actor = item.get("actor_login")
        values = {
            "event_type": item.get("event_type") or "unknown",
            "action": item.get("action"),
            "actor_login": actor,
            "member_id": _history_member_id(members_by_login, [actor]),
            "repository": item.get("repository") or GITHUB_REPOSITORY,
            "title": str(item.get("title") or "GitHub event")[:512],
            "url": item.get("url"), "reference": item.get("reference"),
            "occurred_at": item.get("occurred_at") or now, "received_at": now,
            "payload_summary_json": json.dumps({
                "source": "history", "action": item.get("action"),
                "number": item.get("number"), "reference": item.get("reference"),
            }, ensure_ascii=False),
        }
        if row:
            for field, value in values.items():
                setattr(row, field, value)
            updated += 1
        else:
            row = ProjectGithubEvent(delivery_id=delivery_id, **values)
            db.add(row)
            inserted += 1
        event_type = values["event_type"]
        counts[event_type] = counts.get(event_type, 0) + 1
        created, completed = _sync_history_task(db, item, admin, members_by_login, req.import_tasks)
        tasks_created += int(created)
        tasks_completed += int(completed)

    audit_project(db, admin, "sync_history", "github", None, {
        "days": req.days, "import_tasks": req.import_tasks,
        "events": len(items), "tasks_created": tasks_created,
    })
    db.commit()
    return {
        "status": "ok", "since": since, "events_found": len(items),
        "events_inserted": inserted, "events_updated": updated,
        "tasks_created": tasks_created, "tasks_completed": tasks_completed,
        "counts": counts,
    }


@router.post("/integrations/github/webhook", status_code=202)
async def github_webhook(
    request: Request,
    db: Session = Depends(get_db),
    signature: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    event_type: str | None = Header(default=None, alias="X-GitHub-Event"),
    delivery_id: str | None = Header(default=None, alias="X-GitHub-Delivery"),
):
    if not GITHUB_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="GitHub Webhook 尚未配置")
    body = await request.body()
    expected = "sha256=" + hmac.new(GITHUB_WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Webhook 签名无效")
    if not event_type or not delivery_id:
        raise HTTPException(status_code=400, detail="Webhook 请求头不完整")
    if db.query(ProjectGithubEvent).filter(ProjectGithubEvent.delivery_id == delivery_id).first():
        return {"status": "duplicate"}
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Webhook JSON 无效") from exc
    repository = (payload.get("repository") or {}).get("full_name") or ""
    if GITHUB_REPOSITORY and repository.casefold() != GITHUB_REPOSITORY.casefold():
        raise HTTPException(status_code=403, detail="Webhook 仓库不匹配")
    summary = _github_summary(event_type, payload)
    member = db.query(ProjectMember).filter(ProjectMember.github_login == summary["actor"]).first() if summary["actor"] else None
    event = ProjectGithubEvent(
        delivery_id=delivery_id, event_type=event_type, action=summary["action"],
        actor_login=summary["actor"], member_id=member.id if member else None,
        repository=repository, title=summary["title"], url=summary["url"],
        reference=summary["reference"], occurred_at=summary["occurred_at"], received_at=utcnow(),
        payload_summary_json=json.dumps({
            "action": summary["action"], "number": summary["number"], "reference": summary["reference"]
        }, ensure_ascii=False),
    )
    db.add(event)
    if event_type == "pull_request" and summary["action"] == "closed" and (payload.get("pull_request") or {}).get("merged"):
        task = db.query(ProjectTask).filter(ProjectTask.github_pr_number == summary["number"]).first()
        if task:
            task.status, task.progress, task.updated_at = "done", 100, utcnow()
    if event_type == "issues" and summary["action"] == "closed":
        task = db.query(ProjectTask).filter(ProjectTask.github_issue_number == summary["number"]).first()
        if task:
            task.status, task.progress, task.updated_at = "done", 100, utcnow()
    db.commit()
    return {"status": "accepted"}
