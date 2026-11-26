def decide(actor, owner):
    if actor is None:
        return 401
    return 200 if actor == owner else 403

if __name__ == '__main__':
    print([decide(actor, 'north') for actor in (None, 'south', 'north')])
