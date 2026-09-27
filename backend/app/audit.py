from psycopg2.extras import Json

from .database import get_cursor


def record_audit(user: dict | None, action: str, resource: str | None = None,
                 resource_id: int | None = None, details: dict | None = None):
    actor = user or {"id": None, "username": "system", "role": "system"}
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO audit_logs
               (user_id, username, role, action, resource, resource_id, details)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (actor["id"], actor["username"], actor["role"], action,
             resource, resource_id, Json(details) if details is not None else None),
        )
