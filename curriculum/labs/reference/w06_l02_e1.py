import sqlite3


def solve(db: sqlite3.Connection, document_id: int, key: str) -> tuple[int, str]:
    if type(document_id) is not int or document_id < 1 or not key.strip():
        raise ValueError('invalid job identity')
    with db:
        db.execute("INSERT INTO jobs(document_id,op_key,status) VALUES (?,?,'queued') ON CONFLICT(document_id,op_key) DO NOTHING", (document_id, key))
        row = db.execute('SELECT id,status FROM jobs WHERE document_id = ? AND op_key = ?', (document_id, key)).fetchone()
        if row is None:
            raise RuntimeError('job missing after insert')
        return (row[0], row[1])
