-- Run once on an existing LungTic MySQL database, after phase2/phase2b.
-- Existing patients intentionally remain unassigned until an administrator reviews them.
USE lungtic;

CREATE TABLE IF NOT EXISTS departments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(128) NOT NULL UNIQUE
) ENGINE=InnoDB;

ALTER TABLE patients
    ADD COLUMN primary_department_id INT NULL,
    ADD CONSTRAINT fk_patients_primary_department
        FOREIGN KEY (primary_department_id) REFERENCES departments(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS department_memberships (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    department_id INT NOT NULL,
    is_head BOOLEAN NOT NULL DEFAULT FALSE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE KEY uq_department_member (user_id, department_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS patient_care_assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    user_id INT NOT NULL,
    department_id INT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE KEY uq_patient_care (patient_id, user_id, department_id),
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS access_grants (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    grantee_user_id INT NOT NULL,
    granted_by_user_id INT NOT NULL,
    purpose VARCHAR(256) NOT NULL,
    can_write BOOLEAN NOT NULL DEFAULT FALSE,
    starts_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,
    revoked_at DATETIME NULL,
    INDEX ix_grants_grantee (grantee_user_id, patient_id, expires_at),
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (grantee_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (granted_by_user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS clinical_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    study_id INT NULL,
    record_type VARCHAR(32) NOT NULL,
    title VARCHAR(256) NOT NULL,
    original_filename VARCHAR(256) NOT NULL,
    media_type VARCHAR(128) NOT NULL,
    storage_key VARCHAR(128) NOT NULL UNIQUE,
    size_bytes BIGINT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    uploaded_by_user_id INT NOT NULL,
    version INT NOT NULL DEFAULT 1,
    patient_visible BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL,
    INDEX ix_records_patient_time (patient_id, created_at),
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (study_id) REFERENCES studies(id) ON DELETE SET NULL,
    FOREIGN KEY (uploaded_by_user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS audit_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    actor_user_id INT NOT NULL,
    patient_id INT NULL,
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(32) NOT NULL,
    resource_id INT NULL,
    allowed BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL,
    INDEX ix_audit_patient_time (patient_id, created_at),
    FOREIGN KEY (actor_user_id) REFERENCES users(id),
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE SET NULL
) ENGINE=InnoDB;
