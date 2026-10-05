from strings_util import is_palindrome


def test_simple():
    assert is_palindrome("level")


def test_ignores_case_and_spaces():
    assert is_palindrome("A man a plan a canal Panama")


def test_not_palindrome():
    assert not is_palindrome("hello")
