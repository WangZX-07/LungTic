-- Apply once after phase5_internal_notifications.sql.
USE lungtic;

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
