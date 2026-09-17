-- Apply once after phase3.sql. Existing attachments remain version 0
-- until the offline encrypt_legacy_records.py migration is completed.
USE lungtic;

ALTER TABLE clinical_records
    ADD COLUMN ciphertext_sha256 CHAR(64) NULL,
    ADD COLUMN encryption_version TINYINT NOT NULL DEFAULT 0,
    ADD COLUMN key_id VARCHAR(32) NULL,
    ADD COLUMN wrapped_key VARCHAR(128) NULL,
    ADD COLUMN wrap_nonce VARCHAR(32) NULL,
    ADD COLUMN file_nonce VARCHAR(32) NULL,
    ADD COLUMN file_tag VARCHAR(32) NULL;
