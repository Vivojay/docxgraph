import json
from datetime import datetime

from fastapi import Request
from sqlalchemy.orm import Session

from ..models import AuditLog, User
from ..services.firebase_store import upsert_audit_document


def log_audit_event(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str | int | None = None,
    user: User | None = None,
    request: Request | None = None,
    org_id: int | None = None,
    metadata: dict | None = None,
) -> None:
    event = AuditLog(
        org_id=org_id if org_id is not None else (user.org_id if user else None),
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
        metadata_json=json.dumps(metadata) if metadata else None,
    )
    db.add(event)
    timestamp = datetime.utcnow().isoformat()
    upsert_audit_document(
        f"{timestamp}:{action}:{entity_type}:{entity_id if entity_id is not None else 'none'}",
        {
            "org_id": event.org_id,
            "user_id": event.user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id) if entity_id is not None else None,
            "ip_address": event.ip_address,
            "user_agent": event.user_agent,
            "metadata": metadata or {},
            "created_at": timestamp,
        },
    )
