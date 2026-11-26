import sqlite3

if __name__ == '__main__':
    with sqlite3.connect(':memory:') as db:
        rows = db.execute('WITH d(id) AS (VALUES (8), (1), (3), (5)) SELECT id FROM d WHERE id > ? ORDER BY id LIMIT ?', (1, 2)).fetchall()
        print(rows)
