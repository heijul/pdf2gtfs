import sys
from filecmp import cmp
from pathlib import Path

from ghostscript import GhostscriptError
from pdfminer.pdfparser import PDFSyntaxError

from config import Config
from reader import (
    _preprocess_check, get_chars_dataframe, dataframe_to_rows, get_pages,
    Reader,
    sniff_page_count)

from test import get_test_src_dir, P2GTestCase


# See https://stackoverflow.com/questions/62455023/mock-import-failure
# noinspection PyUnusedLocal,PyMissingTypeHints,PyMethodMayBeStatic
class ImportRaiser:
    def find_spec(self, fullname, path, target=None):
        if fullname == 'ghostscript':
            # we get here if the module is not loaded and not in sys.modules
            raise ImportError()


class Test(P2GTestCase):
    @classmethod
    def setUpClass(cls: P2GTestCase, **kwargs) -> None:
        super().setUpClass(False, True)

    def setUp(self) -> None:
        super().setUp()
        Config.preprocess = False

    def test_get_chars_dataframe(self) -> None:
        ...

    def test_sniff_page_count(self) -> None:
        self.assertEqual(6, sniff_page_count(Config.filename))
        file_path = get_test_src_dir().joinpath("data/rmv_u1.pdf")
        self.assertEqual(4, sniff_page_count(file_path))

    def test_get_pages(self) -> None:
        ...

    def test_split_line_into_fields(self) -> None:
        ...

    def test_split_df_into_lines(self) -> None:
        ...

    def test_dataframe_to_rows(self) -> None:
        Config.pages = "all"
        pages = list(get_pages(Config.filename))
        self.assertEqual(6, len(pages))
        line_count = [76, 78, 77, 74, 78, 49]
        for i in range(len(pages)):
            with self.subTest(msg=i):
                lines = dataframe_to_rows(get_chars_dataframe(pages[i]))
                self.assertEqual(line_count[i], len(lines))

    def test_get_pdf_tables_from_df(self) -> None:
        ...

    def test_pdt_tables_to_timetables(self) -> None:
        ...

    def test_page_to_timetables(self) -> None:
        ...

    def test__preprocess_check(self) -> None:
        Config.preprocess = False
        self.assertFalse(_preprocess_check())
        Config.preprocess = True
        self.assertTrue(_preprocess_check())

        reload = False
        if "ghostscript" in sys.modules:
            reload = True
            del sys.modules["ghostscript"]
        sys.meta_path.insert(0, ImportRaiser())
        self.assertFalse(_preprocess_check())
        # Import ghostscript again if we removed it before.
        if reload:
            try:
                sys.meta_path.pop(0)
                from ghostscript import Ghostscript
            except RuntimeError:
                pass

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


class TestReader(P2GTestCase):
    @classmethod
    def setUpClass(cls: P2GTestCase, **kwargs) -> None:
        super().setUpClass(True, True)

    def test__remove_preprocess_tempfile(self) -> None:
        reader = Reader()
        reader.preprocess()
        self.assertIsNotNone(reader.tempfile)
        self.assertTrue(Path(reader.tempfile.name).exists())
        reader._remove_preprocess_tempfile()
        self.assertFalse(Path(reader.tempfile.name).exists())

    def test_preprocess(self) -> None:
        reader = Reader()
        try:
            reader.preprocess()
        except GhostscriptError:
            self.fail("GhostscriptError raised")
        file_path = Path(reader.tempfile.name)
        self.assertTrue(file_path.exists())
        # Assert input and output are different.
        self.assertFalse(cmp(file_path, Path(Config.filename), True))

    def test_get_pages(self) -> None:
        reader = Reader()
        reader.preprocess()
        Config.pages = "1-3"
        pages = list(reader.get_pages())
        self.assertEqual(3, len(pages))

        invalid_pdf = self.temp_path.joinpath("invalid_pdf.pdf")
        with open(invalid_pdf, "wb") as file:
            file.write(b"Invalid pdf file")
        reader._remove_preprocess_tempfile()
        reader.tempfile = None
        reader.filepath = invalid_pdf
        with self.assertRaises(PDFSyntaxError):
            list(reader.get_pages())

    def test_assert_valid_pages(self) -> None:
        reader = Reader()
        Config.pages = "666"
        with self.assertRaises(SystemExit):
            reader.assert_valid_pages()
        try:
            Config.pages = "all"
            reader.assert_valid_pages()
            Config.pages = "1-5"
            reader.assert_valid_pages()
        except SystemExit:
            self.fail("Valid pages are not invalid")

    def test_read(self) -> None:
        ...
