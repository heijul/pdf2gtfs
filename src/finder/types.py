from typing import TYPE_CHECKING, TypeAlias


if TYPE_CHECKING:
    from finder.cluster import Cluster, Node

StopName: TypeAlias = str
Clusters: TypeAlias = dict[StopName: list["Cluster"]]
Route: TypeAlias = list["Node"]
Routes: TypeAlias = list[Route]
StopNames: TypeAlias = list[StopName]
