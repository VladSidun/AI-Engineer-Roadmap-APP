import csv
from io import StringIO

if __name__ == "__main__":
    fixture = StringIO('name,count\n"Paper, A4",2\n')
    for record in csv.DictReader(fixture):
        print(record["name"], int(record["count"]), sep=" | ")
