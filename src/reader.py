import logging
import os
import sys
from operator import attrgetter
from pathlib import Path
from shutil import copyfile
from tempfile import NamedTemporaryFile
from time import time
from typing import Any, Iterator, TypeAlias

import pandas as pd
from ghostscript import GhostscriptError
from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTChar, LTPage, LTTextBox, LTTextLine
from pdfminer.pdfparser import PDFSyntaxError

from config import Config
from datastructures.rawtable.field import Field
from datastructures.rawtable.table import (
    cleanup_tables, Row, split_rows_into_tables, Table)
from datastructures.timetable.table import TimeTable
from p2g_types import Char


PDF_READ_ERROR_CODE = 2

logger = logging.getLogger(__name__)


Line: TypeAlias = list[Char]
Lines: TypeAlias = list[Line]


def get_chars_dataframe(page: LTPage) -> pd.DataFrame:
    def _fix_text(text: str) -> str:
        # Fix chars which were turned into codes during preprocessing.
        if len(text) == 1:
            return text
        try:
            # Broken chars have this format: 'cid(x)' where x is a number.
            return chr(int(text[5:-1]))
        except TypeError:
            logger.debug("Encountered charcode '{text}' with length "
                         "{len(text)}, but could not convert it to char.")

    def cleanup_df(_df: pd.DataFrame) -> pd.DataFrame:
        # Round to combat possible tolerances in the coordinates.
        _df = _df.round({"x0": 2, "x1": 2, "y0": 2, "y1": 2})
        # Skip objects which are not on the page.
        return _df[(_df["x0"] < _df["x1"]) & (_df["y0"] < _df["y1"]) &
                   (_df["x0"] >= page.x0) & (_df["x1"] <= page.x1) &
                   (_df["y0"] >= page.y0) & (_df["y1"] <= page.y1)]

    def _unpack_char(element: LTChar) -> dict[str: Any]:
        return {"x0": element.x0,
                "x1": element.x1,
                "y0": page.y1 - element.y1,
                "y1": page.y1 - element.y1 + element.height,
                "text": _fix_text(element.get_text())
                }

    def _get_char_list() -> list[dict]:
        # Can't use LTTextLine because it depends on pdfminers layout
        #  algorithm, which merges fields of different columns, making
        #  it impossible at times to properly detect column annotations.
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
                    char = _unpack_char(textline_element)
                    # Ignore vertical text
                    if not textline_element.upright:
                        msg = ("Char(text='{text}', x0={x0:.2f}, y0="
                               "{y0:.2f}, x1={x1:.2f}, y1={y1:.2f})")
                        logger.debug(f"Skipping vertical char:\n\t"
                                     f"{msg.format(**char)}")
                        continue
                    char_list.append(_unpack_char(textline_element))
        return char_list

    df = cleanup_df(pd.DataFrame(_get_char_list()))

    # Change type to reduce memory usage.
    text_dtype = pd.CategoricalDtype(set(df["text"]))
    df["text"] = df["text"].astype(text_dtype)

    return df


def get_pages(file: str | Path) -> Iterator[LTPage]:
    # Disable advanced layout analysis.
    laparams = LAParams(boxes_flow=None)
    return extract_pages(
        file, laparams=laparams, page_numbers=Config.pages.page_ids)


def split_line_into_fields(line: Line) -> list[Field]:
    """ Split the given chars into fields,
    merging multiple fields, based on their x coordinates. """
    fields = []
    if len(line) == 0:
        return fields

    # Fields are semi-continuous streams of chars. May not be strictly
    #  continuous, because we rounded the coordinates.
    for char in sorted(line, key=attrgetter("x0")):
        char_field = Field.from_char(char)
        new_field = not fields or not fields[-1].is_next_to(char_field)
        if new_field:
            fields.append(char_field)
            continue
        fields[-1].add_char(char)

    return fields


def split_df_into_lines(df: pd.DataFrame) -> Lines:
    """ Turn the df into a list of Line. A list of chars is part of the same
    line if the pairwise y0-distance between the chars is less than a max. """

    line_y0 = 0
    lines: Lines = []
    max_char_distance = round((df["y1"] - df["y0"]).mean()) / 2
    for val in df.sort_values(["y0", "x0"]).itertuples(False, "Char"):
        new_line = abs(val.y0 - line_y0) > max_char_distance
        if new_line:
            line_y0 = val.y0
            lines.append([])
        lines[-1].append(val)

    return lines


def dataframe_to_rows(char_df: pd.DataFrame) -> list[Row]:
    rows = []
    start = time()

    for line in split_df_into_lines(char_df):
        row = Row.from_fields(split_line_into_fields(line))
        rows.append(row)

    logger.info(f"Processing of rows took: "
                f"{time() - start:.3f} seconds.")
    return rows


def get_raw_tables_from_df(char_df: pd.DataFrame) -> list[Table]:
    rows = dataframe_to_rows(char_df)
    raw_tables = cleanup_tables(split_rows_into_tables(rows))
    return raw_tables


def raw_tables_to_timetables(raw_tables) -> list[TimeTable]:
    timetables = []
    for table in raw_tables:
        table.fix_split_stopnames()
        timetables.append(table.to_timetable())
    return timetables


def page_to_timetables(page: LTPage) -> list[TimeTable]:
    char_df = get_chars_dataframe(page)
    raw_tables = get_raw_tables_from_df(char_df)
    tables = raw_tables_to_timetables(raw_tables)

    logger.info(f"Number of tables found: {len(tables)}")
    return tables


class Reader:
    def __init__(self) -> None:
        self.tempfile = None
        self.filepath = Path(Config.filename).resolve()

    def __del__(self) -> None:
        self._remove_preprocess_tempfile()

    def _remove_preprocess_tempfile(self) -> None:
        if not self.tempfile:
            return
        try:
            os.unlink(self.tempfile.name)
        except OSError:
            pass

    def preprocess(self) -> None:
        """ Remove invisible text (most likely used for OCR/etc.), while also
        significantly improving performance, cause only text is preserved. """
        if not _preprocess_check():
            return

        from ghostscript import Ghostscript

        logger.info("Beginning preprocessing...")
        start = time()
        self.tempfile = NamedTemporaryFile(delete=False)
        # GS can't use open files as outfiles (may be system dependent).
        self.tempfile.close()

        # FEATURE: Allow custom args
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
            raise e
        logger.info(f"Preprocessing done. Took {time() - start:.2f}s")

    def get_pages(self) -> Iterator[LTPage]:
        """ Return the pdfminer page iterator, which is lazy. """
        file = self.tempfile.name if self.tempfile else self.filepath
        try:
            return get_pages(file)
        except PDFSyntaxError as e:
            logger.error(f"PDFFile '{file}' could not be read. Are you sure "
                         "it's a valid pdf file? This may also sometimes "
                         "happen for no apparent reason. Please try again.")
            logger.error(e)
            sys.exit(PDF_READ_ERROR_CODE)

    def read(self) -> list[TimeTable]:
        """ Return the timetables from all given pages. """
        self.preprocess()

        timetables = []
        start = time()
        for page in self.get_pages():
            page_num = Config.pages.page_num(page.pageid)
            logger.info(f"Basic reading of page {page_num} took: "
                        f"{time() - start:.4} seconds.")
            timetables += page_to_timetables(page)
            start = time()

        return timetables


def _preprocess_check() -> bool:
    """ Check if we could theoretically preprocess the pdf. """
    if not Config.preprocess:
        logger.info("Preprocessing was disabled via config. "
                    "Continuing with raw pdf file...")
        return False
    try:
        from ghostscript import Ghostscript
        return True
    except RuntimeError:
        logger.warning("Ghostscript library does not seem to be "
                       "installed. Skipping preprocessing...")
        return False
