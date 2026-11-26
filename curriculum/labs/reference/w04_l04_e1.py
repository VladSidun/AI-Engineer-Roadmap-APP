import sqlite3


def solve(db: sqlite3.Connection, tenant: str, after: int, limit: int) -> tuple[list[int], int | None]:
    if type(after) is not int or type(limit) is not int or after < 0 or not 1 <= limit <= 50:
        raise ValueError('invalid pagination')
    rows = db.execute('SELECT id FROM documents WHERE tenant = ? AND id > ? ORDER BY id LIMIT ?',
                      (tenant, after, limit + 1)).fetchall()
    ids = [row[0] for row in rows[:limit]]
    return ids, ids[-1] if len(rows) > limit else None
