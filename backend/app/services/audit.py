import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.models import WorkflowAuditLog


def canonical_json(data: Optional[Dict[str, Any]]) -> str:
    if not data:
        return "{}"
    return json.dumps(data, sort_keys=True, separators=(',', ':'), default=str)


def format_timestamp(dt: Any) -> str:
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")
    return str(dt or "")


def compute_row_hash(
    prev_hash: Optional[str],
    actor_id: Optional[UUID],
    action: str,
    entity: str,
    entity_id: Optional[UUID],
    old_status: Optional[str],
    new_status: Optional[str],
    remarks: Optional[str],
    payload: Optional[Dict[str, Any]],
    created_at_iso: str
) -> str:
    """Computes tamper-evident SHA-256 row hash per Section 4.1 specification."""
    parts = [
        str(prev_hash or "0000000000000000000000000000000000000000000000000000000000000000"),
        str(actor_id or ""),
        str(action or ""),
        str(entity or ""),
        str(entity_id or ""),
        str(old_status or ""),
        str(new_status or ""),
        str(remarks or ""),
        canonical_json(payload),
        str(created_at_iso)
    ]
    raw_str = "||".join(parts)
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


def write_audit_log(
    db: Session,
    action: str,
    entity: str,
    entity_id: Optional[UUID] = None,
    actor_id: Optional[UUID] = None,
    actor_role: Optional[str] = None,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    remarks: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None
) -> WorkflowAuditLog:
    """Append a cryptographically chained audit log row within the current database transaction."""
    last_log = db.query(WorkflowAuditLog).order_by(WorkflowAuditLog.id.desc()).first()
    prev_hash = last_log.row_hash if last_log else "0000000000000000000000000000000000000000000000000000000000000000"

    now = datetime.now(timezone.utc)
    now_formatted = format_timestamp(now)

    row_hash = compute_row_hash(
        prev_hash=prev_hash,
        actor_id=actor_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        old_status=old_status,
        new_status=new_status,
        remarks=remarks,
        payload=payload,
        created_at_iso=now_formatted
    )

    audit_entry = WorkflowAuditLog(
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        entity=entity,
        entity_id=entity_id,
        old_status=old_status,
        new_status=new_status,
        remarks=remarks,
        payload=payload,
        created_at=now,
        prev_hash=prev_hash,
        row_hash=row_hash
    )
    db.add(audit_entry)
    db.flush()
    return audit_entry


def verify_chain_integrity(db: Session) -> Dict[str, Any]:
    """Recomputes SHA-256 hash chain across all blocks to verify tamper-evident integrity."""
    start_time = time.perf_counter()
    verified_at = datetime.now(timezone.utc)
    logs = db.query(WorkflowAuditLog).order_by(WorkflowAuditLog.id.asc()).all()

    if not logs:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "valid": True,
            "broken_at": None,
            "total_blocks": 0,
            "head_hash": None,
            "verified_at": verified_at,
            "verification_time_ms": elapsed_ms,
            "message": "Empty audit ledger: 0 blocks found. Genesis baseline intact.",
        }

    expected_prev = "0000000000000000000000000000000000000000000000000000000000000000"

    for log in logs:
        # Check previous hash linkage
        if log.prev_hash != expected_prev:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(f"Broken hash link at audit log block id={log.id}")
            return {
                "valid": False,
                "broken_at": log.id,
                "total_blocks": len(logs),
                "head_hash": logs[-1].row_hash if logs else None,
                "verified_at": verified_at,
                "verification_time_ms": elapsed_ms,
                "message": f"Cryptographic link broken at block #{log.id}: predecessor hash mismatch. Requires administrative review.",
            }

        created_at_str = format_timestamp(log.created_at)
        expected_row_hash = compute_row_hash(
            prev_hash=log.prev_hash,
            actor_id=log.actor_id,
            action=log.action,
            entity=log.entity,
            entity_id=log.entity_id,
            old_status=log.old_status,
            new_status=log.new_status,
            remarks=log.remarks,
            payload=log.payload,
            created_at_iso=created_at_str
        )

        if log.row_hash != expected_row_hash:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(f"Tampered row hash detected at audit log block id={log.id}")
            return {
                "valid": False,
                "broken_at": log.id,
                "total_blocks": len(logs),
                "head_hash": logs[-1].row_hash if logs else None,
                "verified_at": verified_at,
                "verification_time_ms": elapsed_ms,
                "message": f"Tampered row detected at block #{log.id}: row digest does not match recomputed SHA-256 hash. Requires administrative review.",
            }

        expected_prev = log.row_hash

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return {
        "valid": True,
        "broken_at": None,
        "total_blocks": len(logs),
        "head_hash": logs[-1].row_hash if logs else None,
        "verified_at": verified_at,
        "verification_time_ms": elapsed_ms,
        "message": f"Cryptographic chain integrity verified across all {len(logs)} blocks with zero anomalies.",
    }
