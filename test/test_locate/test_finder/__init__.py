from typing import TypeAlias

import pandas as pd

from pdf2gtfs.datastructures.gtfs_output.stop import GTFSStopEntry
from pdf2gtfs.locate.finder import Stops

from test.test_locate import create_handler


DF: TypeAlias = pd.DataFrame


def get_stops_and_dummy_df(stop_count: int = 3) -> tuple[list, DF]:
    columns = ["lat", "lon",
               "idx", "stop_id", "names",
               "name_cost", "node_cost"]
    stops = [(f"{i}", f"stop_{i}") for i in range(stop_count)]
    lat_lon = [(round(49 + i / 1000, 4), round(9 + i / 1000, 4))
               for i in range(1, 10)]
    costs = [(i, i % 2) for i in range(9, 18)]

    data = [[lat, lon, i, stop_id, name, node_cost, name_cost]
            for i, ((lat, lon), (stop_id, name), (node_cost, name_cost))
            in enumerate(zip(lat_lon, 3 * stops, costs))]
    df = pd.DataFrame(data, columns=columns)
    return stops, df


def get_stops_from_stops_list(stops_list: list[tuple[str, str]]) -> Stops:
    handler = create_handler()
    route = handler.routes.add("test_route")
    for stop_id, stop_name in stops_list:
        stop = GTFSStopEntry(stop_name, stop_id)
        handler.stops.entries.append(stop)
    stops = Stops(handler, route.route_id, handler.stops.entries)
    return stops
