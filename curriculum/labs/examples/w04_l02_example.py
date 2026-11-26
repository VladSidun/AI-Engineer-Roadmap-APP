import sqlite3

if __name__ == '__main__':
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE records (id INTEGER PRIMARY KEY)')
        try:
            with db:
                db.execute('INSERT INTO records VALUES (1)')
                db.execute('INSERT INTO records VALUES (1)')
        except sqlite3.IntegrityError:
            print('rolled back')
        print(db.execute('SELECT COUNT(*) FROM records').fetchone()[0])
