from config import Config
from reader import get_chars_dataframe, dataframe_to_rows, get_pages, Reader

from test import P2GTestCase


class Test(P2GTestCase):
    def setUp(self) -> None:
        super().setUp()
        Config.preprocess = False
        self.data_dir = Config.p2g_dir.joinpath("src/test/data")
        self.filename = self.data_dir.joinpath("vag_1_preprocessed.pdf")
        Config.filename = str(self.filename)

    def test_read_vag_1_page_1(self) -> None:
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

    def test_get_lines(self) -> None:
        Config.pages = "all"
        pages = list(get_pages(self.filename))
        self.assertEqual(6, len(pages))
        line_count = [76, 78, 77, 74, 78, 49]
        for i in range(len(pages)):
            with self.subTest(msg=i):
                lines = dataframe_to_rows(get_chars_dataframe(pages[i]))
                self.assertEqual(line_count[i], len(lines))

    def test_get_chars_dataframe(self) -> None:
        ...

    def test_sniff_page_count(self) -> None:
        ...

    def test_get_pages(self) -> None:
        ...

    def test_split_line_into_fields(self) -> None:
        ...

    def test_split_df_into_lines(self) -> None:
        ...

    def test_dataframe_to_rows(self) -> None:
        ...

    def test_get_pdf_tables_from_df(self) -> None:
        ...

    def test_pdt_tables_to_timetables(self) -> None:
        ...

    def test_page_to_timetables(self) -> None:
        ...

    def test__preprocess_check(self) -> None:
        ...


class TestReader(P2GTestCase):
    def test__remove_preprocess_tempfile(self) -> None:
        ...

    def test_preprocess(self) -> None:
        ...

    def test_get_pages(self) -> None:
        ...

    def test_assert_valid_pages(self) -> None:
        ...

    def test_read(self) -> None:
        ...
