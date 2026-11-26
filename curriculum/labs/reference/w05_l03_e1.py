import json
from typing import BinaryIO


def solve(stream: BinaryIO, media_type: str, limit: int) -> str:
    if media_type != 'application/json' or type(limit) is not int or limit < 1:
        raise ValueError('unsupported upload boundary')
    data = bytearray()
    while len(data) <= limit:
        chunk = stream.read(min(4096, limit + 1 - len(data)))
        if not chunk:
            break
        data.extend(chunk)
    if len(data) > limit:
        raise ValueError('upload too large')
    value = json.loads(data.decode('utf-8'))
    if not isinstance(value, dict) or set(value) != {'title'}:
        raise ValueError('expected title object')
    title = value['title']
    if not isinstance(title, str) or not title.strip():
        raise ValueError('expected nonblank title')
    return title.strip()
