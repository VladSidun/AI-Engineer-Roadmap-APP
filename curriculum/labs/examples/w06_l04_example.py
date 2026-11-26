if __name__ == '__main__':
    trace = [('demo-1', 'queued'), ('demo-1', 'running'), ('demo-1', 'succeeded')]
    latest = dict(trace)
    print(len(latest), latest['demo-1'])
