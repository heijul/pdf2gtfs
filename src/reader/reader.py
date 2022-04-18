from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

import pandas as pd
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBox, LTChar, LTTextLine

from datastructures.base import Row, field_from_char, table_from_rows


pd.set_option('display.max_colwidth', None)
BASE_DIR = Path("/mnt/gamma/uni/modules/thesis/pdf2gtfs/")


class BaseReader:
    filepath: ClassVar[Path]
    out_path: ClassVar[Path]

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


def contains_bbox(container, bbox):
    return (container[0] <= bbox[0] <= container[2] and
            container[1] <= bbox[1] <= container[3] and
            container[0] <= bbox[2] <= container[2] and
            container[1] <= bbox[3] <= container[3])


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
        for page in extract_pages(self.filepath):
            page_chars = get_chars_dataframe_from_page(page)
            self.get_lines(page_chars)
            break

    def get_lines(self, df: pd.DataFrame):
        # Round to combat tolerances.
        df = df.round({"top": 0, "x0": 2, "x1": 2, "y0": 2, "y1": 2})
        # Chars are in the same row if they have the same distance to top.
        lines = df.groupby("top")
        rows = []
        for group_id in lines.groups:
            line = lines.get_group(group_id)
            rows.append(self.split_line_into_fields(line))
        row_list_to_tables(rows)
        return lines

    def split_line_into_fields(self, line: pd.DataFrame) -> Row:
        fields = []
        if len(line) == 0:
            return Row()

        for _, char in line.iterrows():
            # Ignore vertical text
            if char.upright != 1:
                continue
            # Fields are continuous streams of chars.
            if not fields or char.x0 != fields[-1].x1:
                fields.append(field_from_char(char))
                continue
            fields[-1].add_char(char)
        return Row().from_list(fields)


def row_list_to_tables(rows: list[Row]):
    options = {
        "max_row_distance": 3,
        }

    tables = []
    current_rows = [rows[0]]

    for row in rows[1:]:
        # Ignore rows that are not on page
        # TODO: needs to check other coordinates as well
        if row.y0 < 0:
            continue
        distance_between_rows = abs(row.y1 - current_rows[-1].y0)
        if distance_between_rows > options["max_row_distance"]:
            print(f"Distance between rows: {distance_between_rows}")
            tables.append(table_from_rows(current_rows))
            current_rows = []
        current_rows.append(row)
    return tables


if __name__ == "__main__":
    # noinspection PyPackageRequirements
    fnames = ["./data/vag_linie_eins.pdf", "./data/rmv_u1.pdf",
              "./data/rmv_u1_pdfact_vis.pdf"]
    r_custom = Reader(fnames[0])
    r_custom.read()
