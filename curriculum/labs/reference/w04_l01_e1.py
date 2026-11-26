import sqlite3


def solve(db: sqlite3.Connection, tenant: str) -> list[tuple[int, int]]:
    return db.execute("""
        SELECT d.id, COUNT(j.id) FROM documents AS d
        LEFT JOIN jobs AS j ON j.document_id = d.id AND j.state = 'succeeded'
        WHERE d.tenant = ? GROUP BY d.id ORDER BY d.id
    """, (tenant,)).fetchall()
