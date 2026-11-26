from http import HTTPStatus

if __name__ == '__main__':
    print(int(HTTPStatus.ACCEPTED), HTTPStatus.ACCEPTED.phrase)
    for state in ('queued', 'running', 'succeeded'):
        print(state, state == 'succeeded')
