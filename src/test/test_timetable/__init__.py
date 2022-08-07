from datastructures.timetable.stops import Stop


def create_stops(count: int = 3):
    # TODO: Move to test_timetable/stops
    stops = []
    for i in range(count):
        stops.append(Stop(f"stop{i}", i))
    return stops
