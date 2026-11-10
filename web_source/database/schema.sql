-- LungTic Database Schema
-- MySQL 8.0+

CREATE DATABASE IF NOT EXISTS lungtic CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE lungtic;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role ENUM('doctor','admin','patient') DEFAULT 'doctor',
    patient_code VARCHAR(32) NULL,
    email VARCHAR(128) NULL,
    phone VARCHAR(20) NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE patients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_code VARCHAR(32) NOT NULL UNIQUE,
    age_range VARCHAR(16),
    gender CHAR(1),
    user_id INT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE studies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    study_uid VARCHAR(128) NOT NULL UNIQUE,
    study_date DATE,
    phase_count INT DEFAULT 10,
    tici_path VARCHAR(512) NULL,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE series (
    id INT AUTO_INCREMENT PRIMARY KEY,
    study_id INT NOT NULL,
    series_uid VARCHAR(128),
    phase_index INT NOT NULL,
    slice_count INT,
    FOREIGN KEY (study_id) REFERENCES studies(id) ON DELETE CASCADE,
    CHECK (phase_index BETWEEN 0 AND 9)
) ENGINE=InnoDB;

CREATE TABLE slices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    series_id INT NOT NULL,
    file_path VARCHAR(512),
    slice_index INT,
    z_position FLOAT,
    FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE segmentations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    slice_id INT NOT NULL UNIQUE,
    mask_path VARCHAR(512),
    dice_score FLOAT,
    model_version VARCHAR(32),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (slice_id) REFERENCES slices(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE igtv_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    study_id INT NOT NULL UNIQUE,
    volume_cc FLOAT,
    mesh_path VARCHAR(512),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (study_id) REFERENCES studies(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE trajectories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    study_id INT NOT NULL,
    phase_index INT NOT NULL,
    x_pos FLOAT,
    y_pos FLOAT,
    z_pos FLOAT,
    is_predicted TINYINT DEFAULT 0,
    FOREIGN KEY (study_id) REFERENCES studies(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE user_models (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    model_type ENUM('pth','onnx') NOT NULL,
    task_type ENUM('segmentation','prediction') NOT NULL,
    file_path VARCHAR(512),
    is_active TINYINT DEFAULT 0,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE oauth_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    provider VARCHAR(32) NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    expires_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE password_resets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token VARCHAR(12) NOT NULL,
    expires_at DATETIME NOT NULL,
    used TINYINT DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Migration: add tici_path to existing studies table if needed
-- ALTER TABLE studies ADD COLUMN tici_path VARCHAR(512) NULL;

-- Create the first admin with backend/bootstrap_admin.py and an environment-provided password.

-- Initial schema includes the Phase 3 organization and clinical record tables.
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
    ciphertext_sha256 CHAR(64) NULL,
    encryption_version TINYINT NOT NULL DEFAULT 0,
    key_id VARCHAR(32) NULL,
    wrapped_key VARCHAR(128) NULL,
    wrap_nonce VARCHAR(32) NULL,
    file_nonce VARCHAR(32) NULL,
    file_tag VARCHAR(32) NULL,
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

CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    kind VARCHAR(32) NOT NULL,
    title VARCHAR(128) NOT NULL,
    message VARCHAR(512) NOT NULL,
    target_path VARCHAR(256) NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL,
    INDEX ix_notifications_user_read_time (user_id, is_read, created_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS smtp_settings (
    id TINYINT PRIMARY KEY,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    host VARCHAR(255) NOT NULL,
    port INT NOT NULL,
    security VARCHAR(16) NOT NULL,
    username VARCHAR(255) NOT NULL,
    from_address VARCHAR(255) NOT NULL,
    password_ciphertext TEXT NOT NULL,
    password_nonce VARCHAR(32) NOT NULL,
    key_id VARCHAR(32) NOT NULL,
    updated_at DATETIME NOT NULL,
    updated_by_user_id INT NULL,
    FOREIGN KEY (updated_by_user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;
