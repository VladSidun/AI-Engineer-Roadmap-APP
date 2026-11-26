from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    key: str
    title: str

if __name__ == "__main__":
    rows = [Document("a", "draft"), Document("b", "note"), Document("a", "final")]
    by_key = {}
    for doc in rows:
        by_key.setdefault(doc.key, doc.title)
    print(by_key)
