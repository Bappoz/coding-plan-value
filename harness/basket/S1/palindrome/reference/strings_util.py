import re


def is_palindrome(s):
    normalized = re.sub(r"[^a-z0-9]", "", s.lower())
    return normalized == normalized[::-1]
