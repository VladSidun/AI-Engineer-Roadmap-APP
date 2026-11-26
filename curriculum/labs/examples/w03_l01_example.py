from http import HTTPStatus

if __name__ == '__main__':
    for code in (201, 204, 409):
        print(code, HTTPStatus(code).phrase)
