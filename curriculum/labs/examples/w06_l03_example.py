import math

if __name__ == '__main__':
    values = sorted([20, 200, 40, 10, 30])
    print(values[math.ceil(.5 * len(values)) - 1])
    print(values[math.ceil(.95 * len(values)) - 1])
