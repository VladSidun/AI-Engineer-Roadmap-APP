from io import BytesIO

if __name__ == '__main__':
    for fixture in (b'four', b'fives'):
        stream = BytesIO(fixture)
        print('accepted' if len(stream.read(5)) <= 4 else 'too large')
