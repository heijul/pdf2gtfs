from __future__ import annotations

from typing import TypeAlias

from config import Config


OSMKey: TypeAlias = str
GoodValues: TypeAlias = dict[OSMKey: dict[str: int]]
BadValues: TypeAlias = dict[OSMKey: list[str]]


def get_all_cat_scores() -> tuple[GoodValues, BadValues]:
    osm_value = get_osm_value()
    return osm_value.good_values, osm_value.bad_values


def get_osm_values() -> dict[str: OSMValue]:
    return {"Tram": Tram,
            "StreetCar": StreetCar,
            "LightRail": LightRail,
            "Subway": Subway,
            "Metro": Metro,
            "Rail": Rail,
            "Bus": Bus,
            "Ferry": Ferry,
            "CableTram": CableTram,
            "AerialLift": AerialLift,
            "SuspendedCableCar": SuspendedCableCar,
            "Funicular": Funicular,
            "Trolleybus": Trolleybus,
            "Monorail": Monorail}


def get_osm_value() -> OSMValue:
    return get_osm_values()[Config.gtfs_routetype.name]()


class OSMValue:
    key: str
    bad_values: BadValues

    def __init__(self) -> None:
        self.good_values = self._get_good_values()
        self.bad_values = self._get_bad_values()

    def _get_good_values(self) -> GoodValues:
        return {}

    def _get_bad_values(self) -> BadValues:
        return {}


class Tram(OSMValue):
    def _get_good_values(self) -> GoodValues:
        return {"tram": {"yes": 0},
                "light_rail": {"yes": 1},
                "station": {"light_rail": 1},
                "railway": {"tram_stop": 0, "halt": 2,
                            "station": 2, "platform": 2},
                "train": {"yes": 2}}

    def _get_bad_values(self) -> BadValues:
        return {"tram": ["no"]}

    @property
    def key(self) -> str:
        return "tram"


class StreetCar(Tram):
    pass


class LightRail(OSMValue):
    def _get_good_values(self) -> GoodValues:
        return {
            "light_rail": {"yes": 0},
            "station": {"light_rail": 0},
            "tram": {"yes": 0},
            "railway": {"tram_stop": 0, "halt": 1,
                        "station": 1, "platform": 1},
            "train": {"yes": 1}}

    def _get_bad_values(self) -> BadValues:
        return {"light_rail": ["no"]}


class Subway(OSMValue):
    def _get_good_values(self) -> GoodValues:
        return {"subway": {"yes": 0},
                "train": {"yes": 1},
                "station": {"subway": 0, "train": 1},
                "railway": {"halt": 0, "station": 1, "platform": 1}}

    def _get_bad_values(self) -> BadValues:
        return {"subway": ["no"]}


class Metro(Subway):
    pass


class Rail(OSMValue):
    def _get_good_values(self) -> GoodValues:
        return {"train": {"yes": 0},
                "station": {"train": 0},
                "railway": {"halt": 0, "station": 1, "platform": 1}}

    def _get_bad_values(self) -> BadValues:
        return {"train": ["no"]}


class Bus(OSMValue):
    def _get_good_values(self) -> GoodValues:
        return {"bus": {"yes": 0},
                "amenity": {"bus_station": 0},
                "highway": {"bus_stop": 0, "platform": 1},
                "trolleybus": {"yes": 2}}

    def _get_bad_values(self) -> BadValues:
        return {"bus": ["no"]}


class Ferry(OSMValue):
    def _get_good_values(self) -> GoodValues:
        return {"ferry": {"yes": 0},
                "amenity": {"ferry_terminal": 0}}

    def _get_bad_values(self) -> BadValues:
        return {"ferry": ["no"]}


class CableTram(OSMValue):
    def _get_good_values(self) -> GoodValues:
        return {"tram": {"yes": 1},
                "light_rail": {"yes": 1},
                "train": {"yes": 2},
                "railway": {"halt": 2, "tram_stop": 1,
                            "station": 2, "platform": 2},
                "station": {"light_rail": 3}}


class AerialLift(OSMValue):
    pass


class SuspendedCableCar(AerialLift):
    pass


class Funicular(OSMValue):
    def _get_good_values(self) -> GoodValues:
        return {"railway": {"funicular": 0, "light_rail": 1},
                "station": {"funicular": 0},
                "light_rail": {"yes": 2}}


class Trolleybus(OSMValue):
    def _get_good_values(self) -> GoodValues:
        return {"trolleybus": {"yes", 0},
                "bus": {"yes": 1},
                "amenity": {"bus_station": 1},
                "highway": {"bus_stop": 1, "platform": 1}}

    def _get_bad_values(self) -> BadValues:
        return {"trolleybus": ["no"]}


class Monorail(OSMValue):
    def _get_good_values(self) -> GoodValues:
        return {"monorail": {"yes": 0},
                "station": {"monorail": 1},
                "railway": {"halt": 1, "platform": 1, "station": 2},
                "light_rail": {"yes": 2}}

    def _get_bad_values(self) -> BadValues:
        return {"monorail": ["no"]}
