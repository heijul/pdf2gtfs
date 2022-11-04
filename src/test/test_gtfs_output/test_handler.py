from datetime import datetime, timedelta

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