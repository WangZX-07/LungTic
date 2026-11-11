"""Database models for the isolated LungTic project progress portal."""

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint

from database import Base


class ProjectMember(Base):
    __tablename__ = "project_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feishu_open_id = Column(String(128), unique=True, nullable=False, index=True)
    feishu_union_id = Column(String(128), nullable=True, index=True)
    feishu_user_id = Column(String(128), nullable=True, index=True)
    name = Column(String(128), nullable=False)
    avatar_url = Column(String(512), nullable=True)
    department_ids_json = Column(Text, nullable=False, default="[]")
    department_names_json = Column(Text, nullable=False, default="[]")
    job_title_id = Column(String(128), nullable=True)
    job_title_name = Column(String(128), nullable=True)
    mapped_role = Column(String(32), nullable=False, default="unassigned")
    manual_role = Column(String(32), nullable=True)
    github_login = Column(String(128), nullable=True, index=True)
    active = Column(Boolean, nullable=False, default=True)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class ProjectRoleRule(Base):
    __tablename__ = "project_role_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    department_id = Column(String(128), nullable=True)
    job_title_id = Column(String(128), nullable=True)
    job_title_name = Column(String(128), nullable=True)
    role = Column(String(32), nullable=False)
    priority = Column(Integer, nullable=False, default=100)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class ProjectSession(Base):
    __tablename__ = "project_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    csrf_hash = Column(String(64), nullable=False)
    member_id = Column(Integer, ForeignKey("project_members.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False)
    last_seen_at = Column(DateTime, nullable=False)


class ProjectMilestone(Base):
    __tablename__ = "project_milestones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="planned")
    weight = Column(Float, nullable=False, default=1.0)
    start_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_by_member_id = Column(Integer, ForeignKey("project_members.id"), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class ProjectTask(Base):
    __tablename__ = "project_tasks"
    __table_args__ = (
        UniqueConstraint("github_issue_number", name="uq_project_task_github_issue"),
        UniqueConstraint("github_pr_number", name="uq_project_task_github_pr"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    milestone_id = Column(Integer, ForeignKey("project_milestones.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(240), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="todo", index=True)
    priority = Column(String(16), nullable=False, default="medium")
    assignee_member_id = Column(Integer, ForeignKey("project_members.id", ondelete="SET NULL"), nullable=True, index=True)
    due_date = Column(Date, nullable=True)
    weight = Column(Float, nullable=False, default=1.0)
    progress = Column(Integer, nullable=False, default=0)
    github_issue_number = Column(Integer, nullable=True)
    github_pr_number = Column(Integer, nullable=True)
    github_url = Column(String(512), nullable=True)
    created_by_member_id = Column(Integer, ForeignKey("project_members.id"), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class ProjectProgressUpdate(Base):
    __tablename__ = "project_progress_updates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("project_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    member_id = Column(Integer, ForeignKey("project_members.id", ondelete="CASCADE"), nullable=False, index=True)
    progress = Column(Integer, nullable=True)
    completed = Column(Text, nullable=False)
    next_steps = Column(Text, nullable=True)
    blockers = Column(Text, nullable=True)
    evidence_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, index=True)


class ProjectRisk(Base):
    __tablename__ = "project_risks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(240), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(16), nullable=False, default="medium")
    status = Column(String(32), nullable=False, default="open")
    mitigation = Column(Text, nullable=True)
    owner_member_id = Column(Integer, ForeignKey("project_members.id", ondelete="SET NULL"), nullable=True)
    due_date = Column(Date, nullable=True)
    created_by_member_id = Column(Integer, ForeignKey("project_members.id"), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class ProjectDecision(Base):
    __tablename__ = "project_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(240), nullable=False)
    context = Column(Text, nullable=True)
    decision = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="active")
    decided_by_member_id = Column(Integer, ForeignKey("project_members.id", ondelete="SET NULL"), nullable=True)
    created_by_member_id = Column(Integer, ForeignKey("project_members.id"), nullable=False)
    decided_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class ProjectGithubEvent(Base):
    __tablename__ = "project_github_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    delivery_id = Column(String(128), unique=True, nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    action = Column(String(64), nullable=True)
    actor_login = Column(String(128), nullable=True, index=True)
    member_id = Column(Integer, ForeignKey("project_members.id", ondelete="SET NULL"), nullable=True)
    repository = Column(String(255), nullable=False)
    title = Column(String(512), nullable=False)
    url = Column(String(512), nullable=True)
    reference = Column(String(128), nullable=True)
    occurred_at = Column(DateTime, nullable=False, index=True)
    received_at = Column(DateTime, nullable=False)
    payload_summary_json = Column(Text, nullable=False, default="{}")


class ProjectAuditEvent(Base):
    __tablename__ = "project_audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_member_id = Column(Integer, ForeignKey("project_members.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(64), nullable=False)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(Integer, nullable=True)
    detail_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, index=True)
