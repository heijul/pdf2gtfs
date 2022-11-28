import datetime as dt
import platform
from pathlib import Path
from unittest import mock

import user_input.cli as cli
from config import Config
from datastructures.gtfs_output.agency import GTFSAgency, GTFSAgencyEntry
from test import P2GTestCase


def get_path_with_insufficient_permissions() -> str:
    """ Returns a platform-dependent path, where the user (hopefully) has
    not enough permissions for.
    """
    if platform.system().lower() == "windows":
        return "C:/Windows/pdf2gtfs_test/"
    return "/pdf2gtfs_test"


def create_agency(path: Path, num: int, url: str = None, tz: str = None
                  ) -> GTFSAgency:
    if not url:
        url = "https://www.pdf2gtfs.com"
    if not tz:
        tz = "Europe/Berlin"
    agencies = []
    for i in range(num):
        agency_id = f"agency_{i}"
        agency_entry = GTFSAgencyEntry(agency_id, url, tz, agency_id)
        agencies.append(agency_entry.to_output())

    input_file = path.joinpath("agency.txt")
    with open(input_file, "w", encoding="utf-8") as file:
        file.write("agency_id,agency_name,agency_url,agency_timezone")
        file.write("\n" + "\n".join(agencies) + "\n")
    Config.input_files = [input_file]
    return GTFSAgency(path)


class TestCLI(P2GTestCase):
    @classmethod
    def setUpClass(cls: P2GTestCase, **kwargs) -> None:
        kwargs = {"create_temp_dir": True, "disable_logging": True}
        super().setUpClass(**kwargs)

    @mock.patch("user_input.cli.input", create=True)
    def test__get_input(self, mock_input: mock.Mock) -> None:
        def check(answer: str) -> bool:
            return answer == "valid" or answer == ""

        mock_input.side_effect = ["invalid", "invalid", "valid", "invalid"]
        self.assertEqual("invalid", cli._get_input("test", ["invalid"], ""))
        self.assertEqual(1, mock_input.call_count)
        mock_input.reset_mock()
        mock_input.side_effect = ["invalid", "invalid", "valid", "invalid"]
        self.assertEqual("valid", cli._get_input("test", check, ""))
        self.assertEqual(3, mock_input.call_count)

    @mock.patch("user_input.cli.input", create=True)
    def test__get_inputs(self, mock_input: mock.Mock) -> None:
        def check(answer: str) -> bool:
            return answer == "valid" or answer == ""

        mock_input.side_effect = ["valid", "valid", "invalid", "test", ""]
        results = cli._get_inputs("test", check, "")
        self.assertEqual(["valid", "valid"], results)
        self.assertEqual(5, mock_input.call_count)
        mock_input.reset_mock()

        mock_input.side_effect = ["valid", "valid", "invalid", "test", ""]
        results = cli._get_inputs("", ["invalid", "test", ""], "")
        self.assertEqual(["invalid", "test"], results)
        self.assertEqual(5, mock_input.call_count)
        mock_input.reset_mock()

    def test__to_date(self) -> None:
        dates = ["20221004", "20221231", "20220229", "20240229",
                 "no date", ""]
        results = [dt.datetime(2022, 10, 4), dt.datetime(2022, 12, 31),
                   None, dt.datetime(2024, 2, 29), None, None]
        for i in range(len(dates)):
            with self.subTest(i=i):
                self.assertEqual(results[i], cli._to_date(dates[i]))

    @mock.patch("user_input.cli.input", create=True)
    def test__get_annotation_exceptions(self, mock_input: mock.Mock) -> None:
        # Test valid dates.
        dates = [dt.datetime(2022, 10, 4),
                 dt.datetime(2022, 12, 31),
                 dt.datetime(2024, 2, 29)]
        mock_input.side_effect = (
                [date.strftime("%Y%m%d") for date in dates] + [""])
        self.assertEqual(dates, cli._get_annotation_exceptions())
        self.assertEqual(4, mock_input.call_count)
        mock_input.reset_mock()
        # Test invalid dates.
        dates = [dt.datetime(2022, 10, 4),
                 dt.datetime(2022, 12, 31),
                 dt.datetime(2024, 2, 29)]
        mock_input.side_effect = (
                ["20220229", "test"]
                + [date.strftime("%Y%m%d") for date in dates]
                + [""])
        self.assertEqual(dates, cli._get_annotation_exceptions())
        self.assertEqual(6, mock_input.call_count)

    @mock.patch("user_input.cli.input", create=True)
    def test__get_annotation_default(self, mock_input: mock.Mock) -> None:
        mock_input.side_effect = ["y", "n", "y", "n"]
        self.assertEqual(True, cli._get_annotation_default())
        self.assertEqual(False, cli._get_annotation_default())
        self.assertEqual(True, cli._get_annotation_default())
        self.assertEqual(False, cli._get_annotation_default())
        self.assertEqual(4, mock_input.call_count)

    @mock.patch("user_input.cli.input", create=True)
    def test__handle_annotation(self, mock_input: mock.Mock) -> None:
        mock_input.side_effect = ["s", "e", "a"]
        self.assertEqual((True, False), cli._handle_annotation("annot"))
        self.assertEqual((False, False), cli._handle_annotation("annot"))
        self.assertEqual((False, True), cli._handle_annotation("annot"))
        self.assertEqual(3, mock_input.call_count)

    @mock.patch("user_input.cli.input", create=True)
    def test_handle_annotations(self, mock_input: mock.Mock) -> None:
        annots = ["a", "*"]
        # Skip all.
        mock_input.side_effect = ["a", "s"]
        self.assertEqual({}, cli.handle_annotations(annots))
        self.assertEqual(1, mock_input.call_count)
        mock_input.reset_mock()
        # Skip all single.
        mock_input.side_effect = ["s", "s"]
        self.assertEqual({}, cli.handle_annotations(annots))
        self.assertEqual(2, mock_input.call_count)
        mock_input.reset_mock()

        fmt = "%Y%m%d"
        dates = [dt.datetime(2022, 3, 22),
                 dt.datetime(2022, 10, 4)]
        # Single annotation.
        annots = ["*"]
        mock_input.side_effect = ["e", "y", dates[0].strftime(fmt),
                                  dates[1].strftime(fmt), ""]
        result = {"*": (True, dates)}
        self.assertEqual(result, cli.handle_annotations(annots))
        self.assertEqual(5, mock_input.call_count)
        mock_input.reset_mock()
        # Multiple annotations.
        annots = ["*", "a"]
        mock_input.side_effect = ["e", "y", dates[0].strftime(fmt), "",
                                  "e", "n", dates[1].strftime(fmt), ""]
        result = {"*": (True, [dates[0]]), "a": (False, [dates[1]])}
        self.assertEqual(result, cli.handle_annotations(annots))
        self.assertEqual(8, mock_input.call_count)

    @mock.patch("user_input.cli.input", create=True)
    def test_ask_overwrite_existing_file(self, mock_input: mock.Mock) -> None:
        filename = Path(self.temp_dir.name).joinpath("test.zip")
        with open(filename, "w", encoding="utf-8") as fil:
            fil.write("test_ask_overwrite")
        mock_input.side_effect = ["n", "y", "n"]
        self.assertFalse(cli.ask_overwrite_existing_file(filename))
        self.assertTrue(cli.ask_overwrite_existing_file(filename))
        self.assertFalse(cli.ask_overwrite_existing_file(filename))
        self.assertEqual(3, mock_input.call_count)

    def test__get_agency_string(self) -> None:
        widths = [5, 9, 11, 9, 8]
        agency = ["agency_id", "agency_name", "url", "tz"]
        result = "    0 | agency_id | agency_name |       url |       tz"
        self.assertEqual(result, cli._get_agency_string("0", agency, widths))
        result = "   12 | agency_id | agency_name |       url |       tz"
        self.assertEqual(result, cli._get_agency_string("12", agency, widths))
        agency = ["agency_id", "agency_name", "url", "timezone"]
        result = "   12 | agency_id | agency_name |       url | timezone"
        self.assertEqual(result, cli._get_agency_string("12", agency, widths))

    def test__get_agency_header(self) -> None:
        agency = create_agency(Path(self.temp_dir.name), 0)
        result = ["agency_id", "agency_name", "agency_url", "agency_timezone"]
        self.assertEqual(result, cli._get_agency_header(agency))

    def test__get_agency_column_width(self) -> None:
        path = Path(self.temp_dir.name)
        agency = create_agency(path, 1)
        result = [5, 9, 11, 24, 15]
        self.assertEqual(result, cli._get_agency_column_widths(agency))
        agency = create_agency(path, 1, "a", "agency_test_timezone")
        result = [5, 9, 11, 10, 20]
        self.assertEqual(result, cli._get_agency_column_widths(agency))

    def test__get_agency_prompt(self) -> None:
        result = ("Multiple agencies found:\n\t"
                  "index | agency_id | agency_name "
                  "|      agency_url | agency_timezone\n\t"
                  "    0 |  agency_0 |    agency_0 "
                  "| www.example.com |   Europe/Berlin\n\t"
                  "    1 |  agency_1 |    agency_1 "
                  "| www.example.com |   Europe/Berlin\n\t"
                  "    2 |  agency_2 |    agency_2 "
                  "| www.example.com |   Europe/Berlin\n\n"
                  "Please provide the index of the agency you want to use.")
        agency = create_agency(Path(self.temp_dir.name), 3, "www.example.com")
        self.assertEqual(result, cli._get_agency_prompt(agency))

    @mock.patch("user_input.cli.input", create=True)
    def test__select_agency(self, mock_input: mock.Mock) -> None:
        agency = create_agency(Path(self.temp_dir.name), 3)
        mock_input.side_effect = ["1"]
        self.assertEqual(agency.entries[1], cli.select_agency(agency))
        self.assertEqual(1, mock_input.call_count)
        mock_input.reset_mock()
        # IDs need to be between 1 and number of agencies.
        mock_input.side_effect = ["3", "1"]
        self.assertEqual(agency.entries[1], cli.select_agency(agency))
        self.assertEqual(2, mock_input.call_count)

    @mock.patch("user_input.cli.input", create=True)
    def test_create_output_directory(self, mock_input: mock.Mock) -> None:
        # Enable interactive mode.
        Config.non_interactive = False

        # Test failing creation. (Permission error)
        mock_input.side_effect = ["", "", "", "", "q"]
        path = get_path_with_insufficient_permissions()
        Config.output_path = path
        self.assertFalse(Path(path).exists())
        result = cli.create_output_directory()
        self.assertFalse(result)
        self.assertEqual(5, mock_input.call_count)
        self.assertFalse(Path(path).exists())
        mock_input.reset_mock()

        # Test valid creation.
        path = Path(self.temp_dir.name).joinpath("output_dir_test")
        Config.output_path = path
        self.assertFalse(Path(path).exists())
        result = cli.create_output_directory()
        self.assertTrue(result)
        self.assertTrue(Path(path).exists())
        mock_input.reset_mock()

    def test_create_output_directory__non_interactive(self) -> None:
        # Disable interactive mode.
        Config.non_interactive = True

        # Test failing creation. (Permission error)
        path = get_path_with_insufficient_permissions()
        Config.output_path = path
        self.assertFalse(Path(path).exists())
        result = cli.create_output_directory()
        self.assertFalse(result)
        self.assertFalse(Path(path).exists())

        # Test valid creation.
        path = Path(self.temp_dir.name).joinpath(
            "output_dir_test__non_interactive")
        Config.output_path = path
        self.assertFalse(Path(path).exists())
        result = cli.create_output_directory()
        self.assertTrue(result)
        self.assertTrue(Path(path).exists())
