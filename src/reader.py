import logging
import os
from operator import attrgetter
from pathlib import Path
from shutil import copyfile
from tempfile import NamedTemporaryFile
from time import time

import pandas as pd
from ghostscript import GhostscriptError
from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTTextBox, LTChar, LTTextLine, LTPage
from pdfminer.pdfparser import PDFSyntaxError

from config import Config
from datastructures.rawtable.fields import Field
from datastructures.rawtable.table import Row, split_rows_into_tables
from datastructures.timetable.table import TimeTable


logger = logging.getLogger(__name__)


def contains_bbox(container_bbox, bbox):
    return (container_bbox[0] <= bbox[0] <= container_bbox[2] and
            container_bbox[1] <= bbox[1] <= container_bbox[3] and
            container_bbox[0] <= bbox[2] <= container_bbox[2] and
            container_bbox[1] <= bbox[3] <= container_bbox[3])


def get_chars_dataframe_from_page(page: LTPage) -> pd.DataFrame:
    def unpack_char(element: LTChar):
        return {"x0": element.x0,
                "x1": element.x1,
                "y0": page.y1 - element.y1,
                "y1": page.y1 - element.y1 + element.height,
                "top": page.y1 - element.y1,
                "text": element.get_text(),
                "upright": element.upright,
                }

    # Can't use LTTextLine because it depends on pdfminers layout algorithm,
    #  which merges fields of different columns, making it impossible at times
    #  to properly detect column annotations.
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
                # Skip objects which are not on the page.
                if not contains_bbox(page.bbox, textline_element.bbox):
                    continue
                char_list.append(unpack_char(textline_element))

    return pd.DataFrame(char_list)


def get_pages(file):
    # Disable advanced layout analysis.
    laparams = LAParams(boxes_flow=None)
    return extract_pages(
        file, laparams=laparams, page_numbers=Config.pages.page_ids)


def split_line_into_fields(line: list[pd.Series]) -> list[Field]:
    fields = []
    if len(line) == 0:
        return fields

    for char in sorted(line, key=attrgetter("x0")):
        # Ignore vertical text
        if not char.upright:
            msg = (f"Char(text='{char.text}', x0={char.x0:.2f}, y0="
                   f"{char.y0:.2f}, x1={char.x1:.2f}, y1={char.y1:.2f})")
            logger.debug(f"Skipping vertical char:\n\t{msg}")
            continue
        if len(char.text) != 1:
            # Sometimes chars are wrongly detected as cid(x) codes...
            # ASK: Problem lies with ghostscript/pdfminer;
            #  Should be fixed there and properly
            char.text = chr(int(char.text[5:-1]))
        # Fields are continuous streams of chars.
        char_field = Field.from_char(char)
        if not fields or not char_field.x_is_close(fields[-1]):
            fields.append(char_field)
            continue
        fields[-1].add_char(char)

    return fields


def get_lines(df: pd.DataFrame) -> list[Row]:
    def group_lines():
        _lines: list[tuple[float, list[pd.Series]]] = []
        for idx, value in df.sort_values("top").iterrows():
            value: pd.Series
            key: float = value["top"]
            if (not _lines or
                    abs(_lines[-1][0] - key) > mean_char_height / 2):
                _lines.append((key, []))
            _lines[-1][1].append(value)
        return _lines

    time_start = time()
    mean_char_height = round((df["y1"] - df["y0"]).mean())

    # Round to combat tolerances.
    df = df.round({"top": 2, "x0": 2, "x1": 2, "y0": 2, "y1": 2})

    rows = []
    for _, line in group_lines():
        row = Row.from_fields(split_line_into_fields(line))
        rows.append(row)
    logger.info(f"Processing of lines took: "
                f"{time() - time_start:.3f} seconds.")
    return rows


def get_tables_from_chars(chars: pd.DataFrame):
    rows = get_lines(chars)
    tables = split_rows_into_tables(rows)
    timetables = []
    for table in tables:
        table.fix_split_stopnames()
        timetables.append(table.to_timetable())
    return timetables


def read_page(page: LTPage) -> list[TimeTable]:
    page_chars = get_chars_dataframe_from_page(page)
    tables = get_tables_from_chars(page_chars)
    logger.info(f"Number of tables found: {len(tables)}")
    return tables


class Reader:
    def __init__(self):
        self.tempfile = None
        self.filepath = Path(Config.filename).resolve()

    def _preprocess_cleanup(self):
        if not self.tempfile:
            return
        try:
            os.unlink(self.tempfile.name)
        except OSError:
            pass

    def preprocess(self):
        # Preprocessing seems to take care of invisible text, while also
        # improving performance by a lot, because only text is preserved.
        logger.info("Beginning preprocessing...")
        start_time = time()
        try:
            from ghostscript import Ghostscript
        except RuntimeError:
            logger.warning("Ghostscript library does not seem to be "
                           "installed. Skipping preprocessing...")
            return
        self.tempfile = NamedTemporaryFile(delete=False)
        self.tempfile.close()

        # FEATURE: Allow custom args
        # CHECK: Currently runs on all pages instead of Config.pages,
        #  however should not make a difference, because of how fast gs is
        gs_args = ["gs", "-sDEVICE=pdfwrite", "-dNOPAUSE", "-dFILTERIMAGE",
                   "-dFILTERVECTOR", "-dPRINTED=true", "-dFitPage",
                   "-dBlackText", "-q", "-dBATCH ",
                   f"-sOutputFile={self.tempfile.name}", str(self.filepath)]

        try:
            Ghostscript(*gs_args)
            if Config.output_pp:
                copyfile(self.tempfile.name,
                         Config.output_dir.joinpath("preprocessed.pdf"))
        except GhostscriptError as e:
            logger.error("Ghostscript encountered an error trying to convert "
                         f"{self.filepath} into {self.tempfile.name}.")
            self._preprocess_cleanup()
            raise e
        logger.info(f"Preprocessing done. Took {time() - start_time:.2f}s")

    def read(self) -> list[TimeTable]:
        if Config.preprocess:
            self.preprocess()
        t = time()
        file = self.tempfile.name if self.tempfile else self.filepath
        timetables = []
        try:
            for page in get_pages(file):
                page_num = Config.pages.page_num(page.pageid)
                logger.info(f"Basic reading of page {page_num} took: "
                            f"{time() - t:.4} seconds.")
                timetables += read_page(page)
                t = time()
        except PDFSyntaxError as e:
            logger.error(f"PDFFile '{file}' could not be read. Are you sure "
                         "it's a valid pdf file? This may also sometimes "
                         "happen for no valid reason. Try again.")
            logger.error(e)
            return []
        finally:
            self._preprocess_cleanup()

        return timetables
