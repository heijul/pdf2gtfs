""" Used to read the pdf file. """

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
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser, PDFSyntaxError

from config import Config
from datastructures.pdftable.field import Field
from datastructures.pdftable.pdftable import (
    cleanup_tables, PDFTable, Row, split_rows_into_tables)
from datastructures.timetable.table import TimeTable
from p2g_types import Char


PDF_READ_ERROR_CODE = 2
INVALID_PAGES_QUIT_CODE = 3

logger = logging.getLogger(__name__)

Line: TypeAlias = list[Char]
Lines: TypeAlias = list[Line]


def get_chars_dataframe(page: LTPage) -> pd.DataFrame:
    """ Returns a dataframe consisting of Chars. """

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
        """ Cleanup the given dataframe.

        Rounds the coordinates and drops any entries outside of the page.
        """
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


def sniff_page_count(file: str | Path) -> int:
    """ Return the number of pages in the given PDF. """

    # TODO: Add error handling, though if this one fails, the whole reading
    #  will probably fail as well.
    with open(file, "rb") as file:
        parser = PDFParser(file)
        document = PDFDocument(parser)
        page_count = document.catalog["Pages"].resolve()["Count"]
    return page_count


def get_pages(file: str | Path) -> Iterator[LTPage]:
    """ Return the lazy iterator over the selected pages. """
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
        fields[-1].append_char(char)

    return fields


def split_df_into_lines(df: pd.DataFrame) -> Lines:
    """ Turn the df into a list of Line. A list of chars is part of the same
    line if the pairwise y0-distance between the chars is less than a max. """

    line_y0 = 0
    lines: Lines = []
    max_char_distance = round((df["y1"] - df["y0"]).mean()) / 2
    for val in df.sort_values(["y0", "x0"]).itertuples(False, "Char"):
        new_line = abs(val.y0 - line_y0) > max_char_distance
        if not lines or new_line:
            line_y0 = val.y0
            lines.append([])
        lines[-1].append(val)

    return lines


def dataframe_to_rows(char_df: pd.DataFrame) -> list[Row]:
    """ Use the char_df to create rows. """
    rows = []
    start = time()

    for line in split_df_into_lines(char_df):
        row = Row.from_fields(split_line_into_fields(line))
        rows.append(row)

    logger.info(f"Processing of rows took: "
                f"{time() - start:.2f} seconds.")
    return rows


def get_pdf_tables_from_df(char_df: pd.DataFrame) -> list[PDFTable]:
    """ Create PDFTables using the char_df. """
    rows = dataframe_to_rows(char_df)
    pdf_tables = cleanup_tables(split_rows_into_tables(rows))
    return pdf_tables


def pdf_tables_to_timetables(pdf_tables: list[PDFTable]) -> list[TimeTable]:
    """ Create TimeTables using the PDFTables"""
    timetables = []
    for table in pdf_tables:
        if table.empty:
            continue
        table.fix_split_stopnames()
        timetables.append(table.to_timetable())
    return timetables


def page_to_timetables(page: LTPage) -> list[TimeTable]:
    """ Extract all timetables from the given page. """
    char_df = get_chars_dataframe(page)
    pdf_tables = get_pdf_tables_from_df(char_df)
    tables = pdf_tables_to_timetables(pdf_tables)

    logger.info(f"Number of tables found: {len(tables)}")
    return tables


def _preprocess_check() -> bool:
    """ Check if we could theoretically preprocess the pdf. """
    if not Config.preprocess:
        logger.info("Preprocessing was disabled via config. "
                    "Continuing with raw pdf file...")
        return False
    try:
        from ghostscript import Ghostscript  # noqa: F401

        return True
    except (ImportError, RuntimeError):
        logger.warning("Ghostscript library does not seem to be "
                       "installed. Skipping preprocessing...")
        return False


class Reader:
    """ Class which oversees the reading of the file and handles
    e.g. the removal of any temporary files. """

    def __init__(self) -> None:
        self.tempfile: NamedTemporaryFile = None
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
        """ Preprocess the PDF, if ghostscript is installed.

        Remove invisible text (most likely used for OCR/etc.), as well as
        images and vector graphics, to improve the performance.
        """
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

    def assert_valid_pages(self) -> None:
        """ Checks that the given pages exist in the PDF, exits if not. """

        page_ids = Config.pages.page_ids
        # All pages.
        if page_ids is None:
            return

        pages = Config.pages.pages
        count = sniff_page_count(self.filepath)
        oob_page_ids = [page_id for page_id in page_ids if page_id > count]
        # No pages are out of bounds.
        if not oob_page_ids:
            return

        oob_pages_string = ", ".join([str(page_id) for page_id in pages])
        msg = (f"The PDF only has {count} {{}}, but the following {{}} "
               f"requested: {oob_pages_string}\n"
               f"Please ensure the pages given exist in the PDF or use "
               f"'all', to read all pages.\nQuitting...")

        given_pages = "page was" if len(oob_page_ids) == 1 else "pages were"
        pdf_pages = "page" if count == 1 else "pages"

        logger.error(msg.format(pdf_pages, given_pages))
        sys.exit(INVALID_PAGES_QUIT_CODE)

    def read(self) -> list[TimeTable]:
        """ Return the timetables from all given pages. """

        self.assert_valid_pages()
        self.preprocess()

        timetables = []
        start = time()
        for page in self.get_pages():
            page_num = Config.pages.page_num(page.pageid)
            logger.info(f"Basic reading of page {page_num} took: "
                        f"{time() - start:.2} seconds.")
            timetables += page_to_timetables(page)
            start = time()

        return timetables
