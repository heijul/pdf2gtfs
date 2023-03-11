""" Contains the methods to query the node costs depending on the routetype.
The keys (e.g. "light_rail", "railway", etc.) are defined in OSM.
See wiki.openstreetmap.org/wiki/key:KEYNAME"""

from __future__ import annotations

from typing import TypeAlias

from pdf2gtfs.config import Config


OSMKey: TypeAlias = str
GoodValues: TypeAlias = dict[OSMKey: dict[str: int]]
BadValues: TypeAlias = dict[OSMKey: list[str]]


# TODO: This works but is done waaay too complicated.


def get_all_cat_scores() -> tuple[GoodValues, BadValues]:
    """ Return all values, which make a node a good or bad match. """
    osm_value = get_osm_values()[Config.gtfs_routetype]()
    return osm_value.good_values, osm_value.bad_values


def get_osm_values() -> dict[str: OSMValue]:
    """ Return all OSMValues. """
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


class OSMValue:
    """ Base class to enable querying for the values of a specific key. """
    bad_values: BadValues

    def __init__(self) -> None:
        self.good_values = {}
        self.bad_values = {}


class Tram(OSMValue):
    """ Trams are rail-based, so rail-specific keys are considered as well. """

    def __init__(self) -> None:
        super().__init__()
        self.good_values = {"tram": {"yes": 0},
                            "light_rail": {"yes": 1},
                            "station": {"light_rail": 1},
                            "railway": {"tram_stop": 0, "halt": 2,
                                        "station": 2, "platform": 2},
                            "train": {"yes": 2}}
        self.bad_values = {"tram": ["no"]}


class StreetCar(Tram):
    """ StreetCars are very closely related to trams. """
    # TODO: Add both Tram and LightRail?
    pass


class LightRail(OSMValue):
    """ Light rail vehicles are rail based like trams,
    but have their own specific values. """

    def __init__(self) -> None:
        super().__init__()
        self.good_values = {"light_rail": {"yes": 0},
                            "station": {"light_rail": 0},
                            "tram": {"yes": 0},
                            "railway": {"tram_stop": 0, "halt": 1,
                                        "station": 1, "platform": 1},
                            "train": {"yes": 1}}
        self.bad_values = {"light_rail": ["no"]}


class Subway(OSMValue):
    """ Subways have their own set of keys, but are rail based as well. """

    def __init__(self) -> None:
        super().__init__()
        self.good_values = {"subway": {"yes": 0},
                            "train": {"yes": 1},
                            "station": {"subway": 0, "train": 1},
                            "railway": {"halt": 0, "station": 1,
                                        "platform": 1}}
        self.bad_values = {"subway": ["no"]}


class Metro(Subway):
    """ Metros are essentially subways. """
    pass


class Rail(OSMValue):
    """ Any rail based keys/values. """

    def __init__(self) -> None:
        super().__init__()
        self.good_values = {"train": {"yes": 0},
                            "station": {"train": 0},
                            "railway": {"halt": 0, "station": 1,
                                        "platform": 1}}
        self.bad_values = {"train": ["no"]}


class Bus(OSMValue):
    """ Busses are street-based, but may use trolleybus stations as well. """

    def __init__(self) -> None:
        super().__init__()
        self.good_values = {"bus": {"yes": 0},
                            "amenity": {"bus_station": 0},
                            "highway": {"bus_stop": 0, "platform": 1},
                            "trolleybus": {"yes": 2}}
        self.bad_values = {"bus": ["no"]}


class Ferry(OSMValue):
    """ Ferry is the only water-based transport vehicle. """

    def __init__(self) -> None:
        super().__init__()
        self.good_values = {"ferry": {"yes": 0},
                            "amenity": {"ferry_terminal": 0}}
        self.bad_values = {"ferry": ["no"]}


class CableTram(OSMValue):
    """ Cabletram is rail-based. """

    def __init__(self) -> None:
        super().__init__()
        self.good_values = {"tram": {"yes": 1},
                            "light_rail": {"yes": 1},
                            "train": {"yes": 2},
                            "railway": {"halt": 2, "tram_stop": 1,
                                        "station": 2, "platform": 2},
                            "station": {"light_rail": 3}}


class AerialLift(OSMValue):
    """ AerialLift has no specific keys/values. """
    # TODO: Not correct. Uses key 'aerialway'
    pass


class SuspendedCableCar(AerialLift):
    """ SuspendedCableCar has no specific keys/values,
    but is similar to an AerialLift. """
    # TODO: Not correct. Uses key 'aerialway'
    pass


class Funicular(OSMValue):
    """ Funicular is rail-based. """

    def __init__(self) -> None:
        super().__init__()
        self.good_values = {"railway": {"funicular": 0, "light_rail": 1},
                            "station": {"funicular": 0},
                            "light_rail": {"yes": 2}}


class Trolleybus(OSMValue):
    """ Trolleybus is both highway-based and has its own keys/values. """

    def __init__(self) -> None:
        super().__init__()
        self.good_values = {"trolleybus": {"yes", 0},
                            "bus": {"yes": 1},
                            "amenity": {"bus_station": 1},
                            "highway": {"bus_stop": 1, "platform": 1}}
        self.bad_values = {"trolleybus": ["no"]}


class Monorail(OSMValue):
    """ Monorail is both rail-based and has its own keys/values. """

    def __init__(self) -> None:
        super().__init__()
        self.good_values = {"monorail": {"yes": 0},
                            "station": {"monorail": 1},
                            "railway": {"halt": 1, "platform": 1,
                                        "station": 2},
                            "light_rail": {"yes": 2}}
        self.bad_values = {"monorail": ["no"]}
