from typing import TypeAlias, TYPE_CHECKING


if TYPE_CHECKING:
    from finder.cluster import Cluster2, Node2

StopName: TypeAlias = str
Clusters: TypeAlias = dict[StopName: list["Cluster2"]]
Route: TypeAlias = list["Node2"]
Routes: TypeAlias = list[Route]
StopNames: TypeAlias = list[StopName]
