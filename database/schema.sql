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

-- admin password: admin123
INSERT INTO users (username, password_hash, role) VALUES
('admin', '$2b$12$LJ3m4ys3Lk0TSwHCpNqrOeY4PfGqFpKvR1nOaHz5f0wQqG3tX1fSu', 'admin');
