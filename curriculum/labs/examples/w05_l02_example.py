if __name__ == '__main__':
    policy = {'viewer': {'read'}, 'editor': {'read', 'update'}}
    print('update' in policy.get('viewer', set()))
    print('update' in policy.get('editor', set()))
