"""Offline migration of phase-3 plaintext attachments to authenticated ciphertext.

Stop the API and back up the database and RECORD_DIR before using --apply.
This script never prints encryption keys or patient content.
"""

import argparse
import os
import re
import uuid
from pathlib import Path

from config import RECORD_DIR
from database import SessionLocal
from models.db_models import ClinicalRecord
from services.record_crypto import IntegrityFailure, load_keyring, seal_upload, verify_record

LEGACY_KEY = re.compile(r"[0-9a-f]{32}\.(pdf|png|jpg|jpeg|tici|dcm)\Z")


def migrate_record(db, record: ClinicalRecord, record_dir: Path) -> bool:
    if record.encryption_version == 1:
        return False
    if record.encryption_version != 0 or not LEGACY_KEY.fullmatch(record.storage_key):
        raise IntegrityFailure("Invalid legacy record metadata")
    old_path = record_dir / record.storage_key
    if not old_path.is_file():
        raise IntegrityFailure("Legacy record file is missing")
    new_key = f"{uuid.uuid4().hex}.enc"
    temp_path = record_dir / f"{new_key}.part"
    final_path = record_dir / new_key
    committed = False
    try:
        with old_path.open("rb") as source:
            sealed = seal_upload(
                source, temp_path, patient_id=record.patient_id, storage_key=new_key
            )
        if sealed.size_bytes != record.size_bytes or sealed.sha256 != record.sha256:
            raise IntegrityFailure("Legacy record SHA-256 or size mismatch")
        if final_path.exists():
            raise IntegrityFailure("Encrypted record path collision")
        os.replace(temp_path, final_path)
        record.storage_key = new_key
        record.ciphertext_sha256 = sealed.ciphertext_sha256
        record.encryption_version = 1
        record.key_id = sealed.key_id
        record.wrapped_key = sealed.wrapped_key
        record.wrap_nonce = sealed.wrap_nonce
        record.file_nonce = sealed.file_nonce
        record.file_tag = sealed.file_tag
        verify_record(record, final_path)
        db.commit()
        committed = True
        old_path.unlink()
        return True
    except Exception:
        db.rollback()
        if not committed and final_path.exists():
            final_path.unlink()
        raise
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Encrypt legacy clinical attachments")
    parser.add_argument("--apply", action="store_true", help="perform the migration after an offline backup")
    args = parser.parse_args()
    if not os.getenv("LUNGTIC_DB_URL") or not os.getenv("LUNGTIC_DATA_DIR"):
        raise SystemExit("Set LUNGTIC_DB_URL and LUNGTIC_DATA_DIR explicitly")
    load_keyring()
    with SessionLocal() as db:
        records = db.query(ClinicalRecord).filter(
            ClinicalRecord.encryption_version == 0
        ).order_by(ClinicalRecord.id).all()
        if not args.apply:
            print(f"{len(records)} legacy attachments require encryption; use --apply after an offline backup")
            return
        completed = 0
        for record in records:
            if migrate_record(db, record, Path(RECORD_DIR)):
                completed += 1
        print(f"Encrypted {completed} legacy attachments")


if __name__ == "__main__":
    main()
