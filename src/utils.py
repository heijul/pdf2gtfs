from typing import TypeVar, TypeAlias


def __uid_generator():
    """ Infinite sequence of ids. """
    next_id = 0
    while True:
        yield next_id
        next_id += 1


# Override the __uid_generator, to ensure uniqueness.
__uid_generator = __uid_generator()


def next_uid():
    """ Returns the next unique id. IDs are shared by all objects. """
    return next(__uid_generator)


def strip_forbidden_symbols(raw_name: str) -> str:
    """ Return a str which only consists of letters and allowed chars. """
    from config import Config

    name = ""
    allowed_chars = Config.allowed_stop_chars
    for char in raw_name:
        if char not in allowed_chars and not char.isalpha():
            continue
        name += char
    return name.strip()


T_ = TypeVar("T_")
PaddedList: TypeAlias = list[T_ | None]


def padded_list(objects: list[T_]) -> tuple[PaddedList, list[T_], PaddedList]:
    left_pad = [None] + objects
    right_pad = objects + [None]
    return left_pad, objects, right_pad


def get_edit_distance(s1, s2):
    """ Uses the Wagner-Fischer Algorithm. """
    s1 = " " + s1.casefold().lower()
    s2 = " " + s2.casefold().lower()
    m = len(s1)
    n = len(s2)
    d = [[0] * n for _ in range(m)]

    for i in range(1, m):
        d[i][0] = i
    for j in range(1, n):
        d[0][j] = j

    for j in range(1, n):
        for i in range(1, m):
            cost = int(s1[i] != s2[j])
            d[i][j] = min(d[i - 1][j] + 1,
                          d[i][j - 1] + 1,
                          d[i - 1][j - 1] + cost)

    return d[m - 1][n - 1]
