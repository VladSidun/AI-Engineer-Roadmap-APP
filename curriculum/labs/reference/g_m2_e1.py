import sqlite3


def solve(db: sqlite3.Connection, document_id: int, tenant: str, key: str) -> tuple[int, int | None, str | None]:
    if type(document_id) is not int or document_id < 1 or not tenant.strip() or not key.strip():
        return 422, None, None
    with db:
        insert = db.execute("""
            INSERT INTO jobs(document_id, op_key, status)
            SELECT id, ?, 'queued' FROM documents WHERE id = ? AND tenant = ?
            ON CONFLICT(document_id, op_key) DO NOTHING
        """, (key, document_id, tenant))
        job = db.execute("""
            SELECT jobs.id, jobs.status FROM jobs JOIN documents ON documents.id = jobs.document_id
            WHERE documents.id = ? AND documents.tenant = ? AND jobs.op_key = ?
        """, (document_id, tenant, key)).fetchone()
        if job is None:
            return 404, None, None
        return (202 if insert.rowcount else 200), job[0], job[1]
