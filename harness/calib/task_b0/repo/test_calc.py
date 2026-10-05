from calc import average


def test_average_integers():
    assert average([1, 2, 3]) == 2


def test_average_needs_float_division():
    assert average([1, 2]) == 1.5
