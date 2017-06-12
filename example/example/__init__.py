from ._native import lib


def test():
    point = lib.example_get_origin()
    return (point.x, point.y)
