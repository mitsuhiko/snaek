from ._native import lib


def test():
    return 'from rust: %d' % lib.example_demo()
