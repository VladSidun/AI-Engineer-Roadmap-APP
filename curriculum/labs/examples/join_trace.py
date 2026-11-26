import argparse
import sqlite3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", type=int, default=1)
    args = parser.parse_args()
    with sqlite3.connect(":memory:") as connection:
        connection.executescript(
            "CREATE TABLE topics (id INTEGER, name TEXT);"
            "CREATE TABLE results (topic_id INTEGER, score INTEGER);"
            "INSERT INTO topics VALUES (1, 'SQL');"
            "INSERT INTO results VALUES (1, 2), (99, 5);"
        )
        rows = connection.execute(
            "SELECT name, score FROM topics JOIN results ON id = topic_id WHERE id = ?",
            (args.topic,),
        ).fetchall()
    print(rows)


if __name__ == "__main__":
    main()
