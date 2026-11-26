import sqlite3

if __name__ == '__main__':
    with sqlite3.connect(':memory:') as db:
        rows = db.execute('WITH d(id) AS (VALUES (1), (2)), j(doc_id) AS (VALUES (1), (1)) SELECT d.id, COUNT(j.doc_id) FROM d LEFT JOIN j ON d.id = j.doc_id GROUP BY d.id ORDER BY d.id')
        print(rows.fetchall())
