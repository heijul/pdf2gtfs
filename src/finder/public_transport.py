from __future__ import annotations

from enum import IntEnum


class TransportType(IntEnum):
    ExistingTransportType = 0
    Station = 1
    Platform = 2
    StopPosition = 3
    Dummy = 4

    def compare(self, other: TransportType) -> int:
        """ -1 if self < other, 0 if self == other, 1 if self > other. """
        return int(self.value > other.value) - int(self.value < other.value)

    @staticmethod
    def get(name: str) -> TransportType:
        name = name.lower().replace(" ", "")
        if name == "station":
            return TransportType.Station
        if name == "platform":
            return TransportType.Platform
        if name == "stop_position":
            return TransportType.StopPosition
