from urllib.parse import urlsplit

if __name__ == '__main__':
    for url in ('postgresql://db:5432/quest', 'http://127.0.0.1:8000/health'):
        parts = urlsplit(url)
        print(parts.hostname, parts.port)
