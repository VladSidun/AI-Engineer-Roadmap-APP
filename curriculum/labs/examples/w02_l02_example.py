import argparse
import json


def read_count(text: str) -> int:
    data = json.loads(text)
    if type(data) is not int or data < 0:
        raise ValueError("expected a non-negative integer")
    return data

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="?", default="15")
    print(read_count(parser.parse_args().text))
