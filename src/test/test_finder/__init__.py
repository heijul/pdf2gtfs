from datastructures.gtfs_output.handler import GTFSHandler
from datastructures.gtfs_output.stop_times import Time


def add_stops_to_handler(handler: GTFSHandler, n: int = 5) -> None:
    for i in range(n):
        handler.stops.add(f"stop_{i}")


def add_calendar_to_handler(handler: GTFSHandler) -> None:
    handler.calendar.add(["1", "2"], set())


def add_routes_to_handler(handler: GTFSHandler, n: int = 2) -> None:
    for i in range(n):
        handler.routes.add(short_name=str(i), long_name=f"route_{i}")


def add_stop_times_to_handler(handler: GTFSHandler, time_to_next: Time = None
                              ) -> None:
    stops = handler.stops.entries
    routes = handler.routes.entries
    service_id = handler.calendar.entries[0].service_id
    for route_idx, route in enumerate(routes):
        # Create trip for route.
        trip = handler.trips.add(service_id, route.route_id)
        current_time = Time(6 * (route_idx + 1))
        route_stops = stops[route_idx:len(stops) - route_idx]

        for stop_idx, stop in enumerate(route_stops):
            handler.stop_times.add(trip.trip_id, stop.stop_id,
                                   stop_idx, current_time)
            if time_to_next is None:
                current_time += Time(minutes=1 + stop_idx * 1)


def create_handler() -> GTFSHandler:
    handler = GTFSHandler()
    add_stops_to_handler(handler)
    add_calendar_to_handler(handler)
    add_routes_to_handler(handler)
    add_stop_times_to_handler(handler)
    return handler
