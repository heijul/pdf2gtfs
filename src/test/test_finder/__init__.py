""" Helper functions used by tests for the locate subpackage."""

from datastructures.gtfs_output.handler import GTFSHandler
from datastructures.gtfs_output.stop_times import Time


def add_stops_to_handler(handler: GTFSHandler, n: int = 5) -> None:
    """ Add n unique stops to the given handler. """
    for i in range(n):
        handler.stops.add(f"stop_{i}")


def add_calendar_to_handler(handler: GTFSHandler) -> None:
    """ Add a calendar, with Tuesday and Wednesday as active days. """
    handler.calendar.add(["1", "2"], set())


def add_routes_to_handler(handler: GTFSHandler, n: int = 2) -> None:
    """ Add n unique routes to the given handler. """
    for i in range(n):
        handler.routes.add(str(i), f"route_{i}")


def add_stop_times_to_handler(handler: GTFSHandler, time_to_next: Time = None
                              ) -> None:
    """ Add stop_times to the given handler.
    Creates both trips and stop_times."""

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
    """ Create a dummy handler and adds some basic data to it. """
    handler = GTFSHandler()
    add_stops_to_handler(handler)
    add_calendar_to_handler(handler)
    add_routes_to_handler(handler)
    add_stop_times_to_handler(handler)
    return handler
