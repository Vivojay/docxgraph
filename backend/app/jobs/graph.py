from sqlalchemy.orm import Session

from ..models import Case
from ..services.retrieval import get_case_tags_map, refresh_case_similarity_edges


def rebuild_case_graph(db: Session, org_id: int | None = None) -> int:
    query = db.query(Case)
    if org_id is not None:
        query = query.filter(Case.org_id == org_id)
    cases = query.all()
    tags_map = get_case_tags_map(db, [case.id for case in cases])
    updated = 0
    for case in cases:
        refresh_case_similarity_edges(db, case, tags_map.get(case.id, []))
        updated += 1
    return updated
