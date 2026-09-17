"""Offline master-key rotation for encrypted clinical attachments."""

import argparse
import os
from pathlib import Path

from config import RECORD_DIR
from database import SessionLocal
from models.db_models import ClinicalRecord
from services.record_crypto import load_keyring, rewrap_record, verify_record


def main() -> None:
    parser = argparse.ArgumentParser(description="Rewrap clinical attachment data keys")
    parser.add_argument("--apply", action="store_true", help="rewrap keys to the active key ID")
    args = parser.parse_args()
    if not os.getenv("LUNGTIC_DB_URL") or not os.getenv("LUNGTIC_DATA_DIR"):
        raise SystemExit("Set LUNGTIC_DB_URL and LUNGTIC_DATA_DIR explicitly")
    active, keys = load_keyring()
    with SessionLocal() as db:
        records = db.query(ClinicalRecord).filter(
            ClinicalRecord.encryption_version == 1,
            ClinicalRecord.key_id != active,
        ).order_by(ClinicalRecord.id).all()
        if not args.apply:
            print(f"{len(records)} attachments need rewrapping to {active}; use --apply after a database backup")
            return
        completed = 0
        for record in records:
            try:
                rewrap_record(record, active, keys)
                verify_record(record, Path(RECORD_DIR) / record.storage_key)
                db.commit()
                completed += 1
            except Exception:
                db.rollback()
                raise
        print(f"Rewrapped {completed} attachment keys to {active}")


if __name__ == "__main__":
    main()
