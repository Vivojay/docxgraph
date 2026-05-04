import os
import tempfile
from sqlalchemy import create_engine, text

import backend.app.db as db_module


def test_ensure_local_schema_adds_missing_case_urgency_column():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3", dir=".")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")

    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE organizations (id INTEGER PRIMARY KEY, name VARCHAR(200) NOT NULL, region VARCHAR(100), created_at DATETIME)"))
            connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255) NOT NULL, hashed_password VARCHAR(255) NOT NULL, role VARCHAR(50) NOT NULL, org_id INTEGER NOT NULL, full_name VARCHAR(200), team_id INTEGER, is_active BOOLEAN, created_at DATETIME, last_login_at DATETIME)"))
            connection.execute(
                text(
                    "CREATE TABLE cases ("
                    "id INTEGER PRIMARY KEY, "
                    "org_id INTEGER NOT NULL, "
                    "author_id INTEGER NOT NULL, "
                    "case_type VARCHAR(50) NOT NULL, "
                    "specialty VARCHAR(200) NOT NULL, "
                    "specialty_domain VARCHAR(200), "
                    "symptoms TEXT NOT NULL, "
                    "demographics TEXT, "
                    "age_bucket VARCHAR(50), "
                    "constraints TEXT, "
                    "resource_setting VARCHAR(120), "
                    "suspected_dx TEXT, "
                    "final_dx TEXT, "
                    "interventions TEXT, "
                    "outcomes TEXT, "
                    "follow_up TEXT, "
                    "what_changed TEXT, "
                    "template_fields TEXT, "
                    "record_schema VARCHAR(100) NOT NULL, "
                    "created_at DATETIME, "
                    "updated_at DATETIME)"
                )
            )

        original_engine = db_module.engine
        original_url = db_module.settings.database_url
        try:
            db_module.engine = engine
            db_module.settings.database_url = f"sqlite:///{db_path}"
            db_module.ensure_local_schema()
        finally:
            db_module.engine = original_engine
            db_module.settings.database_url = original_url

        with engine.connect() as connection:
            columns = {row[1] for row in connection.execute(text("PRAGMA table_info(cases)")).fetchall()}
        assert "urgency" in columns
    finally:
        engine.dispose()
        if os.path.exists(db_path):
            os.remove(db_path)
