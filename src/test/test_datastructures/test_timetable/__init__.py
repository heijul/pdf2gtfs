""" Helper functions, used by the tests for the timetable subpackage. """

from datastructures.timetable.stops import Stop


def create_stops(count: int = 3):
    """ Create count stops. """
    stops = []
    for i in range(count):
        stops.append(Stop(f"stop{i}", i))
    return stops
