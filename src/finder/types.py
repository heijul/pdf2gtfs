from typing import TypeAlias, TYPE_CHECKING


if TYPE_CHECKING:
    from finder.cluster import Cluster2

StopName: TypeAlias = str
Clusters: TypeAlias = dict[StopName: list["Cluster2"]]
