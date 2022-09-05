from datastructures.timetable.stops import Stop


def create_stops(count: int = 3):
    stops = []
    for i in range(count):
        stops.append(Stop(f"stop{i}", i))
    return stops
