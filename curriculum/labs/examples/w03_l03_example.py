if __name__ == '__main__':
    gaps = [min(1.0, 0.1 * 2 ** step) for step in range(5)]
    print([round(seconds, 1) for seconds in gaps])
