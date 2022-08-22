from typing import TYPE_CHECKING, TypeAlias


if TYPE_CHECKING:
    from finder.osm_node import OSMNode

StopName: TypeAlias = str
Route2: TypeAlias = list["OSMNode"]
Routes2: TypeAlias = list[Route2]
StopNames: TypeAlias = list[StopName]
