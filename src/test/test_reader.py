from unittest import TestCase

from config import Config
from reader import Reader, get_pages, get_chars_dataframe_from_page, get_lines


class TestReader(TestCase):
    def setUp(self) -> None:
        Config.preprocess = False
        self.data_dir = Config.base_dir.joinpath("src/test/test_data")
        self.filename = self.data_dir.joinpath("vag_1_preprocessed.pdf")
        Config.filename = str(self.filename)

    def test_read_vag_1_page_1(self):
        Config.pages = "1"
        reader = Reader()
        timetables = reader.read()
        self.assertEqual(3, len(timetables))
        entry_count = [20, 20, 18]
        for i in range(len(timetables)):
            with self.subTest(i=i):
                self.assertEqual(23, len(timetables[i].stops.stops))
                self.assertEqual(23, len(timetables[i].stops.all_stops))
                self.assertEqual(entry_count[i], len(timetables[i].entries))

    def test_get_lines(self):
        Config.pages = "all"
        pages = list(get_pages(self.filename))
        self.assertEqual(6, len(pages))
        line_count = [76, 78, 77, 74, 78, 49]
        for i in range(len(pages)):
            with self.subTest(msg=i):
                lines = get_lines(get_chars_dataframe_from_page(pages[i]))
                self.assertEqual(line_count[i], len(lines))
