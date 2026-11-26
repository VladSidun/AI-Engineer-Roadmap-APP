import sqlite3


def solve(db: sqlite3.Connection, document_id: int, tenant: str, owner: str, title: str) -> int:
    if not title.strip():
        return 422
    with db:
        changed = db.execute('UPDATE documents SET title = ? WHERE id = ? AND tenant = ? AND owner = ?',
                             (title, document_id, tenant, owner)).rowcount
    return 200 if changed == 1 else 404
