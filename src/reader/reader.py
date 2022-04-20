from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBox, LTChar, LTTextLine

from datastructures.internal.field import field_from_char
from datastructures.internal import Row
from datastructures.internal.table import table_from_rows
from utils import contains_bbox


pd.set_option('display.max_colwidth', None)
BASE_DIR = Path("/mnt/gamma/uni/modules/thesis/pdf2gtfs/")


class BaseReader:
    filepath: Path
    out_path: Path

    def __init__(self, filename: str = None):
        if not filename:
            filename = "./data/vag_linie_eins.pdf"
        self.filepath = BASE_DIR.joinpath(Path(filename)).resolve()

        output_name = Path(f"./data/out/{self.filepath.stem}")
        self.out_path = BASE_DIR.joinpath(output_name)

    @abstractmethod
    def read(self):
        pass

    @abstractmethod
    def transform(self):
        pass


def get_chars_dataframe_from_page(page):
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
                char = {"x0": textline_element.x0,
                        "x1": textline_element.x1,
                        "y0": textline_element.y0,
                        "y1": textline_element.y1,
                        "top": page.bbox[3] - textline_element.bbox[3],
                        "text": textline_element.get_text(),
                        "upright": textline_element.upright,
                        }
                char_list.append(char)
    chars = pd.DataFrame(char_list)
    return chars


class Reader(BaseReader, ABC):
    def read(self):
        for i, page in enumerate(extract_pages(self.filepath)):
            if i != 1:
                continue
            page_chars = get_chars_dataframe_from_page(page)
            rows = self.get_lines(page_chars)
            table_rows = split_rows_into_tables(rows)
            create_tables_from_rows(table_rows)
            break

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
    options = {
        "max_row_distance": 3,
        }

    table_rows = []
    current_rows = [rows[0]]

    for row in rows[1:]:
        distance_between_rows = abs(row.y1 - current_rows[-1].y0)
        if distance_between_rows > options["max_row_distance"]:
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


if __name__ == "__main__":
    # noinspection PyPackageRequirements
    fnames = ["./data/vag_linie_eins.pdf", "./data/rmv_u1.pdf",
              "./data/rmv_g10.pdf"]
    reader = Reader(fnames[0])
    reader.read()
