def parse_setting(line: str) -> tuple[str, str]:
    key, sep, value = line.partition("=")
    key, value = key.strip(), value.strip()
    if not sep or not key or not value:
        raise ValueError("expected key=value")
    return key, value
