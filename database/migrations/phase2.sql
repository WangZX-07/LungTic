-- LungTic Phase 2 Migration
-- Run this against existing lungtic database

ALTER TABLE users MODIFY role ENUM('doctor','admin','patient') DEFAULT 'doctor';
ALTER TABLE users ADD COLUMN patient_code VARCHAR(32) NULL AFTER role;
ALTER TABLE users ADD COLUMN email VARCHAR(128) NULL AFTER patient_code;

ALTER TABLE patients ADD COLUMN user_id INT NULL AFTER gender;
ALTER TABLE patients ADD FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS password_resets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token VARCHAR(12) NOT NULL,
    expires_at DATETIME NOT NULL,
    used TINYINT DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;
