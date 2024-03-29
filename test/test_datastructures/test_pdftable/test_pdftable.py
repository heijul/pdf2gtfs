from operator import attrgetter
from pathlib import Path
from typing import Iterator

from pdfminer.layout import LTPage

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.pdftable.bbox import BBox
from pdf2gtfs.datastructures.pdftable.container import Row
from pdf2gtfs.datastructures.pdftable.field import Field
from pdf2gtfs.datastructures.pdftable.pdftable import (
    split_rows_into_tables, Tables)
from pdf2gtfs.reader import (
    preprocess_check, dataframe_to_rows, get_chars_dataframe, Reader)
from test import get_data_gen, P2GTestCase, TEST_DATA_DIR


def create_rows(row_count: int = 5, col_count: int = 3,
                data_fields: bool = True, first_stop: bool = True,
                right_of: list[Row] = None) -> list[Row]:
    """ Create [count] rows with [field_count] fields each.  """

    def get_text() -> str:
        if first_stop and col_num == 0:
            return f"row_{row_num}-col_{col_num}"
        if data_fields:
            return f"{row_num}.{col_num}"
        return f"row_{row_num}-col_{col_num}"

    def get_base() -> tuple[float, float, float, float]:
        if not right_of:
            return 100, 100, 110, 110
        # Don't add base_delta to y0, to start in the same line.
        left_x1 = max(right_of, key=attrgetter("bbox.x1")).bbox.x1
        return (left_x1 + base_delta,
                min(right_of, key=attrgetter("bbox.y0")).bbox.y0,
                left_x1 + base_delta + base_delta,
                min(right_of, key=attrgetter("bbox.y0")).bbox.y0 + base_delta)

    base_delta = 10
    base_x0, y0, base_x1, y1 = get_base()

    rows = []
    for row_num in range(row_count):
        fields = []
        # Reset xs.
        x0, x1 = base_x0, base_x1
        for col_num in range(col_count):
            fields.append(Field(BBox(x0, y0, x1, y1), get_text()))
            x0 += base_delta
            x1 += base_delta
        rows.append(Row.from_fields(fields))
        y0 += base_delta
        y1 += base_delta

    return rows


def create_table_from_data(texts: list[str], bboxes: list[str]
                           ) -> Tables:
    rows = []
    for text, bbox in zip(texts, bboxes, strict=True):
        x0, y0, x1, y1 = map(int, bbox)
        stop_field = Field(BBox(x0, y0, x1, y1), text)
        data_field = Field(BBox(x0 + 50, y0, x1 + 50, y1), "13.37")
        rows.append(Row.from_fields([stop_field, data_field]))
    return split_rows_into_tables(rows)


class TestTable(P2GTestCase):
    reader: Reader = None
    pages: Iterator[LTPage] = None

    @classmethod
    def setUpClass(cls, **kwargs) -> None:
        Config.load_default_config()
        super().setUpClass(True)
        Config.pages = "2"
        Config.filename = str(TEST_DATA_DIR.joinpath("vag_1.pdf"))
        Config.output_pp = True
        Config.output_path = str(Path(cls.temp_dir.name))
        cls.reader = Reader()
        cls.reader.preprocess()
        cls.pages = cls.reader.get_pages()
        cls.char_df = get_chars_dataframe(next(cls.pages))
        cls.get_data_func = get_data_gen(__file__, cls.__name__)

    def test_generate_data_columns_from_rows(self) -> None:
        if not preprocess_check():
            self.skipTest("No ghostscript installed")
        rows = dataframe_to_rows(self.char_df)
        table = split_rows_into_tables(rows)[1]
        table.generate_columns_from_rows()
        for col in table.columns:
            col.type = col._detect_type()
        data = self.get_data_func("test_generate_data_columns_from_rows")
        col_types = data["col_types"]
        cols = data["cols"]
        self.assertEqual(len(col_types), len(table.columns))
        self.assertEqual(len(cols), len(table.columns))
        for i, col in enumerate(table.columns):
            self.assertEqual(int(col_types[i]), col.type.value)
            self.assertEqual(cols[i], [f.text.strip() for f in col.fields])

    def test_fix_split_stop_names(self) -> None:
        Config.min_row_count = 3
        data = self.get_data_func("test_fix_split_stop_names")
        table = create_table_from_data(data["texts"], data["bboxes"])[0]
        table.generate_columns_from_rows()
        table.fix_split_stopnames()

        fields = table.columns[0].fields
        for stop, field in zip(data["stops"], fields, strict=True):
            self.assertEqual(stop, field.text)

    def test_fix_split_stop_names_indented(self) -> None:
        Config.min_row_count = 3
        data = self.get_data_func("test_fix_split_stop_names_indented")
        table = create_table_from_data(data["texts"], data["bboxes"])[0]
        table.generate_columns_from_rows()
        table.fix_split_stopnames()

        fields = table.columns[0].fields
        for stop, field in zip(data["stops"], fields, strict=True):
            self.assertEqual(stop, field.text)

    def test_split_at_stop_columns(self) -> None:
        left_rows = create_rows(5, 3, True)
        left_row_texts = [str(r) for r in left_rows]
        right_rows = create_rows(5, 5, True, right_of=left_rows)
        right_row_texts = [str(r) for r in right_rows]
        rows = [Row.from_fields(r1.fields + r2.fields)
                for r1, r2 in zip(left_rows, right_rows)]
        table = split_rows_into_tables(rows)[0]
        table.generate_columns_from_rows()
        tables = table.split_at_stop_columns()
        self.assertEqual(left_row_texts, [str(r) for r in tables[0].rows])
        self.assertEqual(right_row_texts, [str(r) for r in tables[1].rows])

    def test_split_at_header_rows(self) -> None:
        rows = create_rows(12, 5, True)
        headers = list(Config.header_values.keys())
        rows[0].fields[0].text = headers[0]
        rows[0].update_type()
        rows[5].fields[0].text = headers[1]
        rows[5].update_type()
        top_rows_texts = [str(r) for r in rows[:5]]
        bot_rows_texts = [str(r) for r in rows[5:]]

        table = split_rows_into_tables(rows)[0]
        table.generate_columns_from_rows()
        tables = table.split_at_header_rows()
        self.assertEqual(top_rows_texts, [str(r) for r in tables[0].rows])
        self.assertEqual(bot_rows_texts, [str(r) for r in tables[1].rows])
