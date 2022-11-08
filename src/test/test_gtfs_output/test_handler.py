from datetime import datetime, timedelta

from holidays import country_holidays

from config import Config
from datastructures.gtfs_output.handler import (
    get_gtfs_archive_path,
    get_gtfs_filepaths, GTFSHandler)
from datastructures.gtfs_output.stop_times import Time
from main import get_timetables
from test_gtfs_output import GTFSOutputBaseClass
from test import get_data_gen


class TestHandler(GTFSOutputBaseClass):
    @classmethod
    def setUpClass(cls, name="") -> None:
        super().setUpClass(name)
        Config.preprocess = False
        Config.pages = "1,2,3"
        input_file = "src/test/data/vag_1_preprocessed.pdf"
        Config.filename = str(Config.p2g_dir.joinpath(input_file))
        cls.timetables = get_timetables()
        cls.data_gen = get_data_gen(__file__, cls.__name__)

    def setUp(self) -> None:
        self.handler = GTFSHandler()

    def test_timetable_to_gtfs(self) -> None:
        # Page 1, first table. No repeat columns.
        timetable = get_timetables()[0]
        self.handler.timetable_to_gtfs(timetable)
        self.assertEqual(22, len(self.handler.stops))
        self.assertEqual(20, len(self.handler.trips))
        self.assertEqual(3, len(self.handler.routes))
        self.assertEqual(3, len(self.handler.calendar))
        self.assertEqual(1, len(self.handler.agency))
        self.assertEqual(284, len(self.handler.stop_times))

    def test_timetable_to_gtfs__with_repeat(self) -> None:
        # Page 2, first table. Contains repeat columns.
        timetable = get_timetables()[3]
        self.handler.timetable_to_gtfs(timetable)
        self.assertEqual(22, len(self.handler.stops))
        # Normal trips + first repeat trips + second repeat trips.
        self.assertEqual(18 + 87 + 7, len(self.handler.trips))
        self.assertEqual(2, len(self.handler.routes))
        self.assertEqual(2, len(self.handler.calendar))
        self.assertEqual(1, len(self.handler.agency))
        self.assertEqual(2446, len(self.handler.stop_times))

    def test_add_timetable_stops(self) -> None:
        timetable = self.timetables[6]
        self.assertEqual(0, len(self.handler.stops))
        self.handler.add_timetable_stops(timetable)
        self.assertEqual(23, len(timetable.stops.stops))
        self.assertEqual(22, len(self.handler.stops))

    def test_generate_routes(self) -> None:
        timetable = get_timetables()[6]
        self.handler.add_timetable_stops(timetable)
        self.handler.generate_routes(timetable)
        self.assertEqual(3, len(self.handler.routes))
        route_names = [route.route_long_name for route in self.handler.routes]
        self.assertEqual("Laßbergstraße-Moosweiher", route_names[0])
        self.assertEqual("Laßbergstraße-Runzmattenweg", route_names[1])
        self.assertEqual("Runzmattenweg-Moosweiher", route_names[2])

    def test_generate_stop_times(self) -> None:
        timetable = self.timetables[7]
        self.handler.add_timetable_stops(timetable)
        self.handler.generate_routes(timetable)
        self.assertEqual(0, len(self.handler.stop_times))
        stop_times = self.handler.generate_stop_times(timetable.entries)
        # Prepare data
        data = self.data_gen("test_generate_stop_times")
        data_stop_times = [[Time.from_string(s) for s in times]
                           for times in data["stop_times"]]
        data_stop_times: list[list[Time]]

        # Same number of entries. (One stop appears twice per route)
        self.assertEqual(sum([len(s) for s in data_stop_times]),
                         sum([len(s) for s in stop_times]) + 26)

        for i in range(len(data_stop_times)):
            with self.subTest(i=i):
                j = 0
                trip_times = data_stop_times[i]
                for entry in stop_times[i].entries:
                    self.assertEqual(trip_times[j], entry.arrival_time)
                    j += 1
                    if entry.arrival_time == entry.departure_time:
                        continue
                    self.assertEqual(trip_times[j], entry.departure_time)
                    j += 1

    def test_generate_calendar_dates(self) -> None:
        Config.gtfs_date_bounds = ""
        Config.holiday_code = {"country": "DE", "subdivision": "BW"}
        timetable = self.timetables[7]
        self.handler.add_timetable_stops(timetable)
        self.handler.generate_routes(timetable)
        stop_times = self.handler.generate_stop_times(timetable.entries)
        # Add generated stoptimes to ours.
        for times in stop_times:
            self.handler.stop_times.merge(times)
        self.handler.trips.remove_unused(self.handler.stop_times)
        self.assertEqual(0, len(self.handler.calendar_dates))
        self.handler.generate_calendar_dates()
        holiday_count = len(country_holidays("DE", "BW", datetime.now().year))
        self.assertEqual(12, holiday_count)
        self.assertEqual(holiday_count, len(self.handler.calendar_dates))

    def test_generate_calendar_dates__no_holidays(self) -> None:
        Config.holiday_code = {}
        timetable = self.timetables[7]
        self.handler.add_timetable_stops(timetable)
        self.handler.generate_routes(timetable)
        stop_times = self.handler.generate_stop_times(timetable.entries)
        # Add generated stoptimes to ours.
        for times in stop_times:
            self.handler.stop_times.merge(times)
        self.handler.trips.remove_unused(self.handler.stop_times)
        self.assertEqual(0, len(self.handler.calendar_dates))
        self.handler.generate_calendar_dates()
        self.assertEqual(0, len(self.handler.calendar_dates))

    def test_get_stops_of_route(self) -> None:
        def get_route_ids_from_stop() -> list[str]:
            """ Return all route_ids for every trip the stop is used in. """
            trip_ids = []
            for stop_time in self.handler.stop_times:
                if stop_time.stop_id == stop.stop_id:
                    trip_ids.append(stop_time.trip_id)
            return [trip.route_id for trip in self.handler.trips
                    if trip.trip_id in trip_ids]

        self.handler.timetable_to_gtfs(self.timetables[0])
        route_ids = self.handler.get_sorted_route_ids()
        counts = [22, 16, 7]

        for i in range(len(route_ids)):
            with self.subTest(i=i):
                route_id = route_ids[i]
                stops = self.handler.get_stops_of_route(route_id)
                self.assertEqual(counts[i], len(stops))
                # Each stop is either part of the route or has a different id.
                for stop in self.handler.stops:
                    stop_route_ids = get_route_ids_from_stop()
                    self.assertTrue(stop in stops
                                    or route_id not in stop_route_ids)


class TestHandlerHelpers(GTFSOutputBaseClass):
    def setUp(self) -> None:
        Config.filename = "input_pdf_123"

    def test_get_gtfs_archive_path(self) -> None:
        archive_path = get_gtfs_archive_path()
        self.assertEqual(Config.output_dir, archive_path.parent)
        name = archive_path.name
        self.assertTrue(name.startswith("pdf2gtfs_input_pdf_123"))
        self.assertTrue(name.endswith(".zip"))
        # Need to use timedelta here, as the name is depending on the time.
        date = datetime.today()
        date_from_name = datetime.strptime(
            name, f"pdf2gtfs_input_pdf_123_%Y%m%d_%H%M%S.zip")
        self.assertTrue(abs(date - date_from_name) < timedelta(seconds=3))

    def test_get_gtfs_filepaths(self) -> None:
        names = ["agency.txt", "calendar.txt", "calendar_dates.txt",
                 "routes.txt", "stop_times.txt", "stops.txt", "trips.txt"]

        filepaths = get_gtfs_filepaths()
        for i in range(len(names)):
            with self.subTest(i=i):
                self.assertEqual(names[i], filepaths[i].name)
                self.assertEqual(Config.output_dir, filepaths[i].parent)
