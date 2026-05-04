from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    future=True,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

Base = declarative_base()


SQLITE_ADDITIVE_SCHEMA_PATCHES = {
    "cases": {
        "urgency": "ALTER TABLE cases ADD COLUMN urgency VARCHAR(32)",
    },
}


def _sqlite_column_names(connection, table_name: str) -> set[str]:
    rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def ensure_local_schema() -> None:
    Base.metadata.create_all(bind=engine)
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as connection:
        for table_name, column_patches in SQLITE_ADDITIVE_SCHEMA_PATCHES.items():
            existing_columns = _sqlite_column_names(connection, table_name)
            for column_name, statement in column_patches.items():
                if column_name not in existing_columns:
                    connection.execute(text(statement))
