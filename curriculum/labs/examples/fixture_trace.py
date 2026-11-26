import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default='{"count": 3}')
    args = parser.parse_args()
    data = json.loads(args.fixture)
    try:
        count = data["count"]
    except (TypeError, KeyError):
        parser.error("expected an object with count")
    if type(count) is not int or count < 0:
        parser.error("count must be a nonnegative integer")
    print(f"count={count}")


if __name__ == "__main__":
    main()
