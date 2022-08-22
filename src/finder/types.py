from typing import TYPE_CHECKING, TypeAlias


if TYPE_CHECKING:
    from finder.cluster import Cluster, Node
    from finder.osm_node import OSMNode

StopName: TypeAlias = str
Clusters: TypeAlias = dict[StopName: list["Cluster"]]
Route: TypeAlias = list["Node"]
Routes: TypeAlias = list[Route]
Route2: TypeAlias = list["OSMNode"]
Routes2: TypeAlias = list[Route2]
StopNames: TypeAlias = list[StopName]
