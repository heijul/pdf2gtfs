class Distance:
    def __init__(self, *, m: float = -1, km: float = -1):
        assert m >= 0 or km >= 0
        self.distance = m if m >= 0 else km * 1000

    @property
    def m(self) -> float:
        return self.distance

    @property
    def km(self) -> float:
        return self.distance / 1000

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Distance):
            raise TypeError("Can only compare Distance to Distance.")
        return self.distance == other.distance

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Distance):
            raise TypeError("Can only compare Distance to Distance.")
        return self.distance < other.distance

    def __le__(self, other: object) -> bool:
        return self == other or self < other

    def __gt__(self, other: object) -> bool:
        return self != other and not self < other

    def __ge__(self, other: object) -> bool:
        return self == other or self > other
