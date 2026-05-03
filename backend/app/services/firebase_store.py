import json
from typing import Any

from ..config import settings

_FIRESTORE_CLIENT = None


def firebase_enabled() -> bool:
    return settings.storage_backend.lower() == "firebase"


def get_firestore_client():
    global _FIRESTORE_CLIENT
    if _FIRESTORE_CLIENT is not None:
        return _FIRESTORE_CLIENT
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except Exception:
        return None
    if not firebase_admin._apps:
        if settings.firebase_credentials_json:
            info = json.loads(settings.firebase_credentials_json)
            firebase_admin.initialize_app(credentials.Certificate(info), {"projectId": settings.firebase_project_id})
        elif settings.firebase_credentials_path:
            firebase_admin.initialize_app(
                credentials.Certificate(settings.firebase_credentials_path),
                {"projectId": settings.firebase_project_id},
            )
        else:
            try:
                firebase_admin.initialize_app(options={"projectId": settings.firebase_project_id})
            except Exception:
                return None
    try:
        _FIRESTORE_CLIENT = firestore.client()
    except Exception:
        return None
    return _FIRESTORE_CLIENT


def _collection(name: str):
    client = get_firestore_client()
    if client is None:
        return None
    return client.collection(name)


def upsert_case_document(case_id: int, payload: dict[str, Any]) -> None:
    collection = _collection(settings.firebase_cases_collection)
    if collection is None:
        return
    collection.document(str(case_id)).set(payload, merge=True)


def fetch_case_document(case_id: int) -> dict[str, Any] | None:
    collection = _collection(settings.firebase_cases_collection)
    if collection is None:
        return None
    snapshot = collection.document(str(case_id)).get()
    if not snapshot.exists:
        return None
    return snapshot.to_dict()


def list_case_documents(org_id: int | None = None) -> list[dict[str, Any]]:
    collection = _collection(settings.firebase_cases_collection)
    if collection is None:
        return []
    query = collection
    if org_id is not None:
        query = query.where("org_id", "==", org_id)
    docs = query.stream()
    payload = []
    for doc in docs:
        row = doc.to_dict()
        row["id"] = int(row.get("id", doc.id))
        payload.append(row)
    return payload


def upsert_user_document(user_id: int, payload: dict[str, Any]) -> None:
    collection = _collection(settings.firebase_users_collection)
    if collection is None:
        return
    collection.document(str(user_id)).set(payload, merge=True)


def fetch_user_document(user_id: int) -> dict[str, Any] | None:
    collection = _collection(settings.firebase_users_collection)
    if collection is None:
        return None
    snapshot = collection.document(str(user_id)).get()
    if not snapshot.exists:
        return None
    row = snapshot.to_dict()
    row["id"] = int(row.get("id", user_id))
    return row


def find_user_document_by_email(email: str) -> dict[str, Any] | None:
    collection = _collection(settings.firebase_users_collection)
    if collection is None:
        return None
    docs = collection.where("email", "==", email.lower().strip()).limit(1).stream()
    for doc in docs:
        row = doc.to_dict()
        row["id"] = int(row.get("id", doc.id))
        return row
    return None


def list_user_documents(org_id: int | None = None) -> list[dict[str, Any]]:
    collection = _collection(settings.firebase_users_collection)
    if collection is None:
        return []
    query = collection
    if org_id is not None:
        query = query.where("org_id", "==", org_id)
    payload = []
    for doc in query.stream():
        row = doc.to_dict()
        row["id"] = int(row.get("id", doc.id))
        payload.append(row)
    return payload


def upsert_audit_document(audit_id: str, payload: dict[str, Any]) -> None:
    collection = _collection(settings.firebase_audit_collection)
    if collection is None:
        return
    collection.document(str(audit_id)).set(payload, merge=True)
