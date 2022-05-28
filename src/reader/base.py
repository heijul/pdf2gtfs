from abc import ABC, abstractmethod
from operator import attrgetter
from pathlib import Path

import pandas as pd
# noinspection PyPackageRequirements
from pdfminer.high_level import extract_pages
# noinspection PyPackageRequirements
from pdfminer.layout import LAParams
# noinspection PyPackageRequirements
from pdfminer.layout import LTTextBox, LTChar, LTTextLine, LTPage

from config import Config
from datastructures.internal.rawtable import Table, Row, Field
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
            # TODO: Using LTTextLine instead of chars probably makes more sense
            for textline_element in textbox_element:
                if not isinstance(textline_element, LTChar):
                    continue
                # TODO: Check why this can even happen.
                # Skip objects which are not on the page.
                if not contains_bbox(page.bbox, textline_element.bbox):
                    continue
                # TODO: Find a way to skip invisible text.
                #  Note: Does not seem to be possible as it appears to have
                #  the same color as the visible text?!

                char_list.append(unpack_char(textline_element))

    return pd.DataFrame(char_list)


# TODO: No need for a class here I guess. Just use toplevel functions with
#  the proper access level, or not, in order to make it replaceable.
class Reader(BaseReader, ABC):
    def read(self) -> None:
        # Disable advanced layout analysis.
        laparams = LAParams(boxes_flow=None)

        pages = extract_pages(self.filepath,
                              laparams=laparams,
                              page_numbers=Config.pages.page_numbers)

        for page in pages:
            self.read_page(page)

    def save_pages_to_csv(self, page_num):
        pages = extract_pages(self.filepath, page_numbers=[page_num])
        for page in pages:
            df = get_chars_dataframe_from_page(page)
            df.to_csv(f"page_char_cache_{page_num}.csv")
            df = df.round({"top": 0, "x0": 2, "x1": 2, "y0": 2, "y1": 2})
            df.to_csv(f"page_char_cache_{page_num}_rounded.csv")
            break

    def read_cached_page(self, page_num):
        page_chars = pd.read_csv(f"page_char_cache_{page_num}.csv",
                                 index_col=0)
        tables = self.get_tables_from_chars(page_chars)
        print(tables)

    def read_page(self, page: LTPage):
        page_chars = get_chars_dataframe_from_page(page)
        tables = self.get_tables_from_chars(page_chars)
        print(tables)

    def get_tables_from_chars(self, chars: pd.DataFrame) -> list[Table]:
        rows = self.get_lines(chars)
        tables = Table.split_rows_into_tables(rows)
        for table in tables:
            table.generate_data_columns_from_rows()
            table.to_timetable()
        print("Tables:", len(tables))
        return tables

    def get_lines(self, df: pd.DataFrame) -> list[Row]:
        def normalize(char):
            char["top"] = (round(char["top"] / mean_char_height)
                           * mean_char_height)
            return char

        mean_char_height = round((df["y1"] - df["y0"]).mean())

        # Round to combat tolerances.
        df = df.round({"top": 0, "x0": 2, "x1": 2, "y0": 2, "y1": 2})
        # Chars are in the same row if they have the same distance to top.
        lines = df.apply(normalize, axis=1).groupby("top")

        rows = []
        for group_id in lines.groups:
            try:
                line = lines.get_group(group_id)
            except KeyError:
                continue
            row = Row.from_fields(self.split_line_into_fields(line))
            rows.append(row)
        return rows

    def split_line_into_fields(self, line: pd.DataFrame) -> list[Field]:
        fields = []
        if len(line) == 0:
            return fields

        sorted_line = sorted([f[1] for f in list(line.iterrows())],
                             key=attrgetter("x0"))
        for char in sorted_line:
            # Ignore vertical text
            if not char.upright:
                print(f"Skipping vertical char '{char}'...")
                continue
            # Fields are continuous streams of chars.
            if not fields or char.x0 != fields[-1].bbox.x1:
                fields.append(Field.from_char(char))
                continue
            fields[-1].add_char(char)

        return fields
