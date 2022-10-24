""" Types used by the finder. """
# TODO NOW: Merge with p2g_types?

from typing import NamedTuple, TYPE_CHECKING, TypeAlias

import pandas as pd


if TYPE_CHECKING:
    from finder.location_nodes import Node

Heap: TypeAlias = list["Node"]
DF: TypeAlias = pd.DataFrame
StopPosition = NamedTuple("StopPosition",
                          [("idx", int), ("stop", str), ("names", str),
                           ("lat", float), ("lon", float),
                           ("node_cost", float), ("name_cost", float)])
