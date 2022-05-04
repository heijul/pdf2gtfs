from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd
# noinspection PyPackageRequirements
from pdfminer.high_level import extract_pages
# noinspection PyPackageRequirements
from pdfminer.layout import LTTextBox, LTChar, LTTextLine, LTPage

from config import Config
from datastructures.internal.field import field_from_char
from datastructures.internal import Row
from datastructures.internal.table import table_from_rows
from utils import contains_bbox


pd.set_option('display.max_colwidth', None)


class BaseReader:
    filepath: Path
    out_path: Path

    def __init__(self, filename: str = None):
        if not filename:
            filename = "./data/vag_linie_eins.pdf"
        self.filepath = Config.base_path.joinpath(Path(filename)).resolve()

        output_name = Path(f"./data/out/{self.filepath.stem}")
        self.out_path = Config.base_path.joinpath(output_name)

    @abstractmethod
    def read(self):
        pass

    @abstractmethod
    def transform(self):
        pass


def get_chars_dataframe_from_page(page: LTPage) -> pd.DataFrame:
    def unpack_char(element: LTChar):
        return {"x0": element.x0,
                "x1": element.x1,
                "y0": element.y0,
                "y1": element.y1,
                "top": page.bbox[3] - element.bbox[3],
                "text": element.get_text(),
                "upright": element.upright,
                }

    char_list = []
    for page_element in page:
        if not isinstance(page_element, LTTextBox):
            continue
        for textbox_element in page_element:
            if not isinstance(textbox_element, LTTextLine):
                continue
            for textline_element in textbox_element:
                if not isinstance(textline_element, LTChar):
                    continue
                if not contains_bbox(page.bbox, textline_element.bbox):
                    continue

                char_list.append(unpack_char(textline_element))

    chars = pd.DataFrame(char_list)

    return chars


class Reader(BaseReader, ABC):
    def read(self) -> None:
        for i, page in enumerate(extract_pages(self.filepath), 1):
            if i not in Config.pages:
                continue
            self.read_page(page)

    def read_page(self, page: LTPage):
        page_chars = get_chars_dataframe_from_page(page)
        rows = self.get_lines(page_chars)
        table_rows = split_rows_into_tables(rows)
        create_tables_from_rows(table_rows)

    def get_lines(self, df: pd.DataFrame) -> list[Row]:
        # Round to combat tolerances.
        df = df.round({"top": 0, "x0": 2, "x1": 2, "y0": 2, "y1": 2})
        # Chars are in the same row if they have the same distance to top.
        # TODO: 'by' as function to include top tolerances
        lines = df.groupby("top")
        rows = []
        for group_id in lines.groups:
            line = lines.get_group(group_id)
            rows.append(self.split_line_into_fields(line))
        return rows

    def split_line_into_fields(self, line: pd.DataFrame) -> Row:
        fields = []
        if len(line) == 0:
            return Row()

        for _, char in line.iterrows():
            # Ignore vertical text
            if not char.upright:
                continue
            # Fields are continuous streams of chars.
            if not fields or char.x0 != fields[-1].x1:
                fields.append(field_from_char(char))
                continue
            fields[-1].add_char(char)
        return Row().from_list(fields)


def split_rows_into_tables(rows: list[Row]):
    table_rows = []
    current_rows = [rows[0]]

    for row in rows[1:]:
        distance_between_rows = abs(row.y1 - current_rows[-1].y0)
        if distance_between_rows > Config.max_row_distance:
            print(f"Distance between rows: {distance_between_rows}")
            table_rows.append(current_rows)
            current_rows = []
        current_rows.append(row)
    else:
        if current_rows:
            table_rows.append(current_rows)
    return table_rows


def create_tables_from_rows(table_rows: list[list[Row]]):
    raw_tables = map(table_from_rows, table_rows)
    # Merge raw tables which are close
    ...
    # Handle "wrapper"-tables which are not proper tables (Days, etc.)
    ...
    # Handle annotations TODO: Maybe move to table_from_rows as with header
    ...
    return list(raw_tables)
