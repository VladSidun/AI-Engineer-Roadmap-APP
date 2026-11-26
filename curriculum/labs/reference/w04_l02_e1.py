import sqlite3


def solve(db: sqlite3.Connection, title: str, job_key: str) -> int:
    if not title.strip() or not job_key.strip():
        raise ValueError('title and job key required')
    with db:
        created = db.execute('INSERT INTO documents(title) VALUES (?)', (title,)).lastrowid
        if created is None:
            raise RuntimeError('missing inserted identity')
        db.execute('INSERT INTO jobs(key, document_id) VALUES (?, ?)', (job_key, created))
    return created
