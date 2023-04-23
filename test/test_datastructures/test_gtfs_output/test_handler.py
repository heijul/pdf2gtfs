from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from holidays import country_holidays

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.gtfs_output.agency import (
    GTFSAgency, GTFSAgencyEntry)
from pdf2gtfs.datastructures.gtfs_output.calendar import GTFSCalendar
from pdf2gtfs.datastructures.gtfs_output.calendar_dates import (
    GTFSCalendarDates)
from pdf2gtfs.datastructures.gtfs_output.handler import (
    get_gtfs_archive_path, GTFSHandler)
from pdf2gtfs.datastructures.gtfs_output.routes import GTFSRoutes
from pdf2gtfs.datastructures.gtfs_output.stop import GTFSStopEntry, GTFSStops
from pdf2gtfs.datastructures.gtfs_output.stop_times import GTFSStopTimes, Time
from pdf2gtfs.datastructures.gtfs_output.trips import GTFSTrips
from pdf2gtfs.main import get_timetables
from pdf2gtfs.utils import UIDGenerator

from test import get_data_gen, P2GTestCase, TEST_DATA_DIR


class TestHandler(P2GTestCase):
    @classmethod
    def setUpClass(cls, **kwargs) -> None:
        super().setUpClass(True, True)
        Config.preprocess = False
        Config.pages = "1,2,3"
        input_file = "vag_1_preprocessed.pdf"
        Config.filename = str(TEST_DATA_DIR.joinpath(input_file))
        Config.output_path = cls.temp_path
        cls.timetables = get_timetables()
        cls.data_gen = get_data_gen(__file__, cls.__name__)
        Config.gtfs_date_bounds = ["20220101", "20221231"]

    def setUp(self) -> None:
        self.handler = GTFSHandler()

    @mock.patch("pdf2gtfs.user_input.cli.input", create=True)
    def test_get_default_agency_id(self, mock_select: mock.Mock) -> None:
        mock_select.side_effect = ["0", "1", "2"]
        dummy_agency: GTFSAgencyEntry = self.handler.agency.entries[0]
        agency_id = self.handler.get_default_agency_id()
        self.assertEqual(dummy_agency.agency_id, agency_id)
        agencies = [GTFSAgencyEntry("agency_1", "", ""),
                    GTFSAgencyEntry("agency_1", "", ""),
                    GTFSAgencyEntry("agency_1", "", "")]
        self.handler.agency.entries = agencies
        agency_id = self.handler.get_default_agency_id()
        self.assertEqual(agencies[0].agency_id, agency_id)
        agency_id = self.handler.get_default_agency_id()
        self.assertEqual(agencies[1].agency_id, agency_id)
        agency_id = self.handler.get_default_agency_id()
        self.assertEqual(agencies[2].agency_id, agency_id)

    def test_timetable_to_gtfs(self) -> None:
        # Page 1, first table. No repeat columns.
        timetable = self.timetables[0]
        self.handler.timetable_to_gtfs(timetable)
        self.assertEqual(22, len(self.handler.stops))
        self.assertEqual(20, len(self.handler.trips))
        self.assertEqual(3, len(self.handler.routes))
        self.assertEqual(3, len(self.handler.calendar))
        self.assertEqual(1, len(self.handler.agency))
        self.assertEqual(284, len(self.handler.stop_times))

    def test_timetable_to_gtfs__with_repeat(self) -> None:
        # Page 2, first table. Contains repeat columns.
        timetable = self.timetables[3]
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
        timetable = self.timetables[6]
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
        Config.holiday_code = {"country": "DE", "subdivision": "BW"}
        # Second table of the third page (contains only holiday).
        timetable = self.timetables[7]
        self.handler.add_timetable_stops(timetable)
        self.handler.generate_routes(timetable)
        stop_times = self.handler.generate_stop_times(timetable.entries)
        # Add generated StopTimes to ours.
        for times in stop_times:
            self.handler.stop_times.merge(times)
        self.handler.trips.remove_unused(self.handler.stop_times)
        self.assertEqual(0, len(self.handler.calendar_dates))
        self.handler.generate_calendar_dates()
        holiday_count = len(country_holidays("DE", "BW", 2022))
        self.assertEqual(12, holiday_count)
        # There is only a single calendar_dates entry.
        self.assertEqual(holiday_count, len(self.handler.calendar_dates))

    def test_generate_calendar_dates2(self) -> None:
        Config.holiday_code = {"country": "DE", "subdivision": "BW"}
        # First table of the third page (contains both holiday/non-holiday).
        timetable = self.timetables[6]
        self.handler.add_timetable_stops(timetable)
        self.handler.generate_routes(timetable)
        stop_times = self.handler.generate_stop_times(timetable.entries)
        # Add generated StopTimes to ours.
        for times in stop_times:
            self.handler.stop_times.merge(times)
        self.handler.trips.remove_unused(self.handler.stop_times)
        self.assertEqual(0, len(self.handler.calendar_dates))
        self.handler.generate_calendar_dates()
        holiday_count = len(country_holidays("DE", "BW", 2022))
        self.assertEqual(12, holiday_count)
        # There are five calendar entries ("Samstag", "Sonn- und Feiertag",
        # and 3 more for the annotations).
        self.assertEqual(holiday_count * 5, len(self.handler.calendar_dates))

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

    @mock.patch("pdf2gtfs.user_input.cli.input", create=True)
    def test_add_annotation_dates(self, mocked_input) -> None:
        # Do not clutter calendar_dates.txt
        Config.holiday_code = {}
        Config.non_interactive = False
        self.handler.timetable_to_gtfs(self.timetables[4])
        self.assertEqual(0, len(self.handler.calendar_dates))

        mocked_input.side_effect = ["e", "n", "20221004", "", "s"]
        self.handler.add_annotation_dates()
        self.assertEqual(2, len(self.handler.calendar_dates))
        services = self.handler.calendar.get_with_annot("*")
        # Disabled by default.
        for service in services:
            self.assertFalse(service.monday.active)
            self.assertFalse(service.tuesday.active)
            self.assertFalse(service.wednesday.active)
            self.assertFalse(service.thursday.active)
            self.assertFalse(service.friday.active)
            self.assertFalse(service.saturday.active)
            self.assertFalse(service.sunday.active)
        for entry in self.handler.calendar_dates:
            self.assertEqual("20221004", entry.date)

        mocked_input.side_effect = ["s", "e", "y", "20221010", ""]
        self.handler.add_annotation_dates()
        self.assertEqual(4, len(self.handler.calendar_dates))
        services = self.handler.calendar.get_with_annot("*")
        # At least one service is active.
        for service in services:
            # * was disabled above, which takes precedence.
            if "*" in service.annotations:
                self.assertTrue(not (
                        service.monday.active or service.tuesday.active
                        or service.wednesday.active or service.thursday.active
                        or service.friday.active or service.saturday.active
                        or service.sunday.active))
            else:
                self.assertTrue(
                    service.monday.active or service.tuesday.active
                    or service.wednesday.active or service.thursday.active
                    or service.friday.active or service.saturday.active
                    or service.sunday.active)
        for entry in self.handler.calendar_dates.entries[2:]:
            self.assertEqual("20221010", entry.date)

    def test__remove_unused_routes(self) -> None:
        self.assertEqual(0, len(self.handler.routes))
        self.handler.timetable_to_gtfs(self.timetables[3])
        self.assertEqual(2, len(self.handler.routes))
        self.handler.routes.add("test_route", "test_route")
        self.handler.timetable_to_gtfs(self.timetables[4])
        self.assertEqual(4, len(self.handler.routes))
        # test_route is unused and will be removed.
        self.handler._remove_unused_routes()
        self.assertEqual(3, len(self.handler.routes))

    def test_write_files(self) -> None:
        Config.non_interactive = True
        timetable = self.timetables[0]
        # Reset UIDGenerator.
        UIDGenerator.id = None
        UIDGenerator.skip_ids = set()
        self.handler.timetable_to_gtfs(timetable)

        fps = self.handler.get_gtfs_filepaths()
        Config.output_path = self.temp_path
        for i, fp in enumerate(fps):
            with self.subTest(i=i):
                self.assertFalse(fp.exists())
        self.handler.write_files()
        for i, fp in enumerate(fps):
            with self.subTest(i=i):
                self.assertTrue(fp.exists())
        Config.input_files = fps
        # Reset UIDGenerator.
        UIDGenerator.id = None
        UIDGenerator.skip_ids = set()
        agency = GTFSAgency(self.temp_path)
        self.assertEqual(self.handler.agency, agency)
        calendar = GTFSCalendar(self.temp_path)
        self.assertEqual(self.handler.calendar, calendar)
        calendar_dates = GTFSCalendarDates(self.temp_path)
        self.assertEqual(self.handler.calendar_dates, calendar_dates)
        routes = GTFSRoutes(self.temp_path, self.handler.routes.agency_id)
        self.assertEqual(self.handler.routes, routes)
        stop_times = GTFSStopTimes(self.temp_path)
        self.assertEqual(self.handler.stop_times, stop_times)
        stops = GTFSStops(self.temp_path)
        self.assertEqual(self.handler.stops, stops)
        trips = GTFSTrips(self.temp_path)
        self.assertEqual(self.handler.trips, trips)

    def test_get_gtfs_filepaths(self) -> None:
        names = ["agency.txt", "calendar.txt", "calendar_dates.txt",
                 "routes.txt", "stop_times.txt", "stops.txt", "trips.txt"]

        filepaths = self.handler.get_gtfs_filepaths()
        temp_dir = Path(self.handler.temp_dir.name)
        for i in range(len(names)):
            with self.subTest(i=i):
                filepaths[i].resolve()
                self.assertEqual(names[i], filepaths[i].name)
                self.assertEqual(temp_dir.resolve(), filepaths[i].parent)

    @mock.patch("pdf2gtfs.user_input.cli.input", create=True)
    def test_create_zip_archive(self, mock_input: mock.Mock) -> None:
        mock_input.side_effect = ["y", "n"]
        Config.non_interactive = False
        timetable = self.timetables[0]
        # Reset UIDGenerator.
        UIDGenerator.id = None
        UIDGenerator.skip_ids = set()
        self.handler.timetable_to_gtfs(timetable)
        self.handler.agency.write()
        self.handler.stops.write()
        self.handler.routes.write()
        self.handler.calendar.write()
        self.handler.trips.write()
        self.handler.stop_times.write()
        self.handler.calendar_dates.write()
        fp = get_gtfs_archive_path()
        Config.output_path = fp
        self.assertFalse(fp.exists())
        self.handler.create_zip_archive()
        self.assertTrue(fp.exists())
        try:
            self.handler.create_zip_archive()
        except SystemExit:
            self.fail("SystemExit raised")
        with self.assertRaises(SystemExit):
            self.handler.create_zip_archive()

        Config.non_interactive = True
        with self.assertRaises(SystemExit):
            self.handler.create_zip_archive()
        Config.output_path = fp.parent.joinpath("testtest.zip")
        fp = get_gtfs_archive_path()
        self.assertFalse(fp.exists())
        self.handler.create_zip_archive()
        self.assertTrue(fp.exists())

    def test_add_coordinates(self) -> None:
        ...

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

    def test_get_avg_time_between_stops(self) -> None:
        self.handler.timetable_to_gtfs(self.timetables[3])
        stop_a = self.handler.stops.entries[9]
        stop_b = self.handler.stops.entries[10]
        stop_c = self.handler.stops.entries[11]
        route_id = self.handler.routes.entries[0].route_id
        avg_time_ab = self.handler.get_avg_time_between_stops(
            route_id, stop_a.stop_id, stop_b.stop_id)
        avg_time_bc = self.handler.get_avg_time_between_stops(
            route_id, stop_b.stop_id, stop_c.stop_id)
        avg_time_ac = self.handler.get_avg_time_between_stops(
            route_id, stop_a.stop_id, stop_c.stop_id)
        self.assertEqual(Time(0, 1), avg_time_ab)
        self.assertEqual(Time(0, 2), avg_time_bc)
        self.assertEqual(Time(0, 4, 4), avg_time_ac)
        self.assertLessEqual(avg_time_ab + avg_time_bc, avg_time_ac)

    def test_get_used_stops(self) -> None:
        self.assertEqual([], self.handler.get_used_stops())
        # Can't use .add(), bc that sets used_in_timetable to True.
        self.handler.stops._add(GTFSStopEntry("test_stop"))
        self.assertEqual([], self.handler.get_used_stops())
        self.handler.timetable_to_gtfs(self.timetables[0])
        self.assertEqual(22, len(self.handler.get_used_stops()))
        self.assertEqual(23, len(self.handler.stops))

    def test_get_sorted_route_ids(self) -> None:
        self.handler.timetable_to_gtfs(self.timetables[0])
        route_ids = self.handler.get_sorted_route_ids()
        for i, route_id in enumerate(route_ids[1:], 1):
            with self.subTest(i=i):
                prev_stop_count = self.handler.get_stops_of_route(
                    route_ids[i - 1])
                stop_count = self.handler.get_stops_of_route(route_id)
                self.assertTrue(len(prev_stop_count) >= len(stop_count))

        # Order of adding does not matter.
        self.handler.timetable_to_gtfs(self.timetables[7])
        self.handler.timetable_to_gtfs(self.timetables[4])
        for i, route_id in enumerate(route_ids[1:], 1):
            with self.subTest(i=i):
                prev_stop_count = self.handler.get_stops_of_route(
                    route_ids[i - 1])
                stop_count = self.handler.get_stops_of_route(route_id)
                self.assertTrue(len(prev_stop_count) >= len(stop_count))


class Test(P2GTestCase):
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
            name, "pdf2gtfs_input_pdf_123_%Y%m%d_%H%M%S.zip")
        self.assertTrue(abs(date - date_from_name) < timedelta(seconds=3))
