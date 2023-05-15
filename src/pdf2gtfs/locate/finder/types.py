""" Types used by the locate. """
from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple, TYPE_CHECKING, TypeAlias

import pandas as pd


if TYPE_CHECKING:
    from pdf2gtfs.locate.finder.loc_nodes import Node

Heap: TypeAlias = list["Node"]
DF: TypeAlias = pd.DataFrame

_StopPosition = NamedTuple("StopPosition",
                           [("idx", int), ("stop", str), ("names", str),
                            ("lat", float), ("lon", float),
                            ("node_cost", float), ("name_cost", float),
                            ("ref_ifopt", str), ("wheelchair", str)])


@dataclass
class OSMNode:
    idx: int
    stop: str
    names: str
    lat: float
    lon: float
    node_cost: float
    name_cost: float
    ref_ifopt: str = None
    wheelchair: str = None

    @staticmethod
    def from_named_tuple(t: _StopPosition) -> OSMNode:
        ref_ifopt = t.ref_ifopt if hasattr(t, "ref_ifopt") else None
        wheelchair = t.wheelchair if hasattr(t, "wheelchair") else None
        return OSMNode(t.idx, t.stop_id, t.names, t.lat, t.lon, t.node_cost,
                       t.name_cost, ref_ifopt, wheelchair)


# noinspection PyTypeChecker
DummyOSMNode = OSMNode(None, None, None, None, None, None, None, None, None)
