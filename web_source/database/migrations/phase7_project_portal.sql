-- Phase 7: isolated LungTic project progress portal (MySQL 8.0+)
USE lungtic;

CREATE TABLE IF NOT EXISTS project_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    feishu_open_id VARCHAR(128) NOT NULL UNIQUE,
    feishu_union_id VARCHAR(128) NULL,
    feishu_user_id VARCHAR(128) NULL,
    name VARCHAR(128) NOT NULL,
    avatar_url VARCHAR(512) NULL,
    department_ids_json TEXT NOT NULL,
    department_names_json TEXT NOT NULL,
    job_title_id VARCHAR(128) NULL,
    job_title_name VARCHAR(128) NULL,
    mapped_role VARCHAR(32) NOT NULL DEFAULT 'unassigned',
    manual_role VARCHAR(32) NULL,
    github_login VARCHAR(128) NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    last_synced_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    INDEX ix_project_members_union_id (feishu_union_id),
    INDEX ix_project_members_user_id (feishu_user_id),
    INDEX ix_project_members_github_login (github_login)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS project_role_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    department_id VARCHAR(128) NULL,
    job_title_id VARCHAR(128) NULL,
    job_title_name VARCHAR(128) NULL,
    role VARCHAR(32) NOT NULL,
    priority INT NOT NULL DEFAULT 100,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS project_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    token_hash CHAR(64) NOT NULL UNIQUE,
    csrf_hash CHAR(64) NOT NULL,
    member_id INT NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    last_seen_at DATETIME NOT NULL,
    INDEX ix_project_sessions_member (member_id),
    INDEX ix_project_sessions_expires (expires_at),
    FOREIGN KEY (member_id) REFERENCES project_members(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS project_milestones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'planned',
    weight DOUBLE NOT NULL DEFAULT 1,
    start_date DATE NULL,
    due_date DATE NULL,
    sort_order INT NOT NULL DEFAULT 0,
    created_by_member_id INT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (created_by_member_id) REFERENCES project_members(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS project_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    milestone_id INT NULL,
    title VARCHAR(240) NOT NULL,
    description TEXT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'todo',
    priority VARCHAR(16) NOT NULL DEFAULT 'medium',
    assignee_member_id INT NULL,
    due_date DATE NULL,
    weight DOUBLE NOT NULL DEFAULT 1,
    progress INT NOT NULL DEFAULT 0,
    github_issue_number INT NULL,
    github_pr_number INT NULL,
    github_url VARCHAR(512) NULL,
    created_by_member_id INT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uq_project_task_github_issue (github_issue_number),
    UNIQUE KEY uq_project_task_github_pr (github_pr_number),
    INDEX ix_project_tasks_status (status),
    INDEX ix_project_tasks_assignee (assignee_member_id),
    INDEX ix_project_tasks_milestone (milestone_id),
    FOREIGN KEY (milestone_id) REFERENCES project_milestones(id) ON DELETE SET NULL,
    FOREIGN KEY (assignee_member_id) REFERENCES project_members(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by_member_id) REFERENCES project_members(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS project_progress_updates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NULL,
    member_id INT NOT NULL,
    progress INT NULL,
    completed TEXT NOT NULL,
    next_steps TEXT NULL,
    blockers TEXT NULL,
    evidence_url VARCHAR(512) NULL,
    created_at DATETIME NOT NULL,
    INDEX ix_project_progress_task (task_id),
    INDEX ix_project_progress_member (member_id),
    INDEX ix_project_progress_time (created_at),
    FOREIGN KEY (task_id) REFERENCES project_tasks(id) ON DELETE SET NULL,
    FOREIGN KEY (member_id) REFERENCES project_members(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS project_risks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(240) NOT NULL,
    description TEXT NULL,
    severity VARCHAR(16) NOT NULL DEFAULT 'medium',
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    mitigation TEXT NULL,
    owner_member_id INT NULL,
    due_date DATE NULL,
    created_by_member_id INT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (owner_member_id) REFERENCES project_members(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by_member_id) REFERENCES project_members(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS project_decisions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(240) NOT NULL,
    context TEXT NULL,
    decision TEXT NOT NULL,
    rationale TEXT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    decided_by_member_id INT NULL,
    created_by_member_id INT NOT NULL,
    decided_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    INDEX ix_project_decisions_time (decided_at),
    FOREIGN KEY (decided_by_member_id) REFERENCES project_members(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by_member_id) REFERENCES project_members(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS project_github_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    delivery_id VARCHAR(128) NOT NULL UNIQUE,
    event_type VARCHAR(64) NOT NULL,
    action VARCHAR(64) NULL,
    actor_login VARCHAR(128) NULL,
    member_id INT NULL,
    repository VARCHAR(255) NOT NULL,
    title VARCHAR(512) NOT NULL,
    url VARCHAR(512) NULL,
    reference VARCHAR(128) NULL,
    occurred_at DATETIME NOT NULL,
    received_at DATETIME NOT NULL,
    payload_summary_json TEXT NOT NULL,
    INDEX ix_project_github_type (event_type),
    INDEX ix_project_github_actor (actor_login),
    INDEX ix_project_github_time (occurred_at),
    FOREIGN KEY (member_id) REFERENCES project_members(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS project_audit_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    actor_member_id INT NULL,
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id INT NULL,
    detail_json TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    INDEX ix_project_audit_actor (actor_member_id),
    INDEX ix_project_audit_time (created_at),
    FOREIGN KEY (actor_member_id) REFERENCES project_members(id) ON DELETE SET NULL
) ENGINE=InnoDB;
