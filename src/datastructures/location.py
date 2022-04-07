from dataclasses import dataclass


@dataclass(repr=False)
class Location:
    lat: float
    lon: float

    def __repr__(self):
        return f"Location({self.lat: .5f} {self.lon: .5f})"
