""" Used to read the pdf file. """
from __future__ import annotations

import logging
import os
import sys
from itertools import pairwise
from operator import attrgetter
from pathlib import Path
from shutil import copyfile
from tempfile import NamedTemporaryFile
from time import strptime, time
from typing import (
    cast, Iterator, Optional, Tuple, TypeAlias, Union,
    )

import pandas as pd
from more_itertools import (
    first_true, flatten, partition, prepend, collapse,
    )
from pdfminer.high_level import extract_pages
from pdfminer.layout import (
    LAParams, LTChar, LTPage, LTText, LTTextLine,
    )
from pdfminer.pdfcolor import PDFColorSpace
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdffont import PDFFont
from pdfminer.pdfinterp import PDFGraphicState
from pdfminer.pdfparser import PDFParser, PDFSyntaxError
from pdfminer.utils import Matrix

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.pdftable import Char
from pdf2gtfs.datastructures.pdftable.field import Field as PDFField
from pdf2gtfs.datastructures.table.bounds import Bounds
from pdf2gtfs.datastructures.table.cell import C, Cell, Cs
from pdf2gtfs.datastructures.table.celltype import T
from pdf2gtfs.datastructures.table.table import (
    merge_tables, Table,
    )
from pdf2gtfs.datastructures.pdftable.pdftable import (
    cleanup_tables, PDFTable, Row, split_rows_into_tables,
    )
from pdf2gtfs.datastructures.timetable.table import TimeTable


def ltchar_monkeypatch__init__(
        self,
        matrix: Matrix,
        font: PDFFont,
        fontsize: float,
        scaling: float,
        rise: float,
        text: str,
        textwidth: float,
        textdisp: Union[float, Tuple[Optional[float], float]],
        ncs: PDFColorSpace,
        graphicstate: PDFGraphicState,
        ) -> None:
    """ This monkeypatch is required, to keep access to the font/fontsize. """
    self.font = font
    self.fontsize = fontsize
    return self.default_init(matrix, font, fontsize, scaling, rise, text,
                             textwidth, textdisp, ncs, graphicstate)


# TODO NOW: Use a class instead, to enable code completion?
# noinspection PyTypeChecker
LTChar.default_init = LTChar.__init__
LTChar.__init__ = ltchar_monkeypatch__init__
LTChar.font = None
LTChar.fontsize = None


PDF_READ_ERROR_CODE = 2
INVALID_PAGES_QUIT_CODE = 3

logger = logging.getLogger(__name__)

Line: TypeAlias = list[Char]
Lines: TypeAlias = list[Line]


def _fix_cid_text(text: str) -> str:
    """ Fix chars which were turned into codes during preprocessing. """
    # TODO NOW: This should be done using LTChar.font
    if len(text) == 1:
        return text
    try:
        # Broken chars have this format: 'cid(x)' where x is a number.
        return chr(int(text[5:-1]))
    except (ValueError, TypeError):
        logger.info(f"Encountered charcode '{text}' with length "
                    f"{len(text)}, but could not convert it to char.")


def lt_char_to_dict(lt_char: LTChar, page_height: float
                    ) -> dict[str: str | float]:
    char = {"x0": round(lt_char.x0, 2), "x1": round(lt_char.x1, 2),
            "y0": round(page_height - lt_char.y1, 2),
            "y1": round(page_height - lt_char.y1 + lt_char.height, 2),
            "text": _fix_cid_text(lt_char.get_text())}
    return char


def get_chars_dataframe(page: LTPage) -> pd.DataFrame:
    """ Returns a dataframe consisting of Chars.

    We can't use LTTextLine because it depends on pdfminer's layout algorithm,
    which merges fields of different columns, making it sometimes impossible,
    to properly detect column annotations.
    """

    def cleanup_df(df: pd.DataFrame) -> pd.DataFrame:
        """ Cleanup the given dataframe.

        Rounds the coordinates and drops any entries outside the page.
        """
        # Round to combat possible tolerances in the coordinates.
        df = df.round({"x0": 2, "x1": 2, "y0": 2, "y1": 2})
        # Skip objects which are not on the page.
        return df[(df["x0"] < df["x1"]) & (df["y0"] < df["y1"]) &
                  (df["x0"] >= page.x0) & (df["x1"] <= page.x1) &
                  (df["y0"] >= page.y0) & (df["y1"] <= page.y1)]

    char_list = []
    text_chars = [char for char in collapse(page, base_type=LTChar)
                  if isinstance(char, LTChar)]
    for text_char in text_chars:
        char = lt_char_to_dict(text_char, page.y1)
        # Ignore vertical text.
        if not text_char.upright:
            msg = ("Char(text='{text}', x0={x0:.2f}, "
                   "y0={y0:.2f}, x1={x1:.2f}, y1={y1:.2f})")
            logger.debug(f"Skipping vertical char:\n\t"
                         f"{msg.format(**char)}")
            continue
        char_list.append(char)

    char_df = cleanup_df(pd.DataFrame(char_list))

    # Change type to reduce memory usage.
    text_dtype = pd.CategoricalDtype(set(char_df["text"]))
    char_df["text"] = char_df["text"].astype(text_dtype)

    return char_df


def split_line_into_words(line: LTTextLine) -> list[list[LTChar]]:
    """ Create lists of chars, that each belong to the same word.

    Iteratively check if a whitespace char (or LTAnnot) is between two
    consecutive chars, to decide if they belong to the same word.

    :param line: The line to split.
    :type line: LTTextLine
    :return: A list of words (= LTChar lists)
    :rtype: List[List[LTChar]]
    """
    def different_font(char1: LTText | None, char2: LTChar) -> bool:
        """ Check if the chars have different font properties. """
        if char1 is None or not isinstance(char1, LTChar):
            return True
        if char1.fontname != char2.fontname:
            return True
        if char1.fontsize != char2.fontsize:
            return True
        if char1.font != char2.font:
            return True
        return False

    def is_word_split(char1: LTChar) -> bool:
        """ Check if the given char is a word split (i.e., whitespace). """
        return char1.get_text() in (" ", "\n")

    words: list[list[LTChar]] = []
    # Do not prefilter line, because LTAnno may be used as word split.
    for prev_char, char in pairwise(prepend(None, line)):
        not_char = not isinstance(char, LTChar)
        if not_char or is_word_split(char) or different_font(prev_char, char):
            words.append([])
        if not_char:
            continue
        words[-1].append(char)
    # Drop empty words.
    return list(filter(bool, words))


def word_contains_time(word: list[LTChar]) -> bool:
    word_text = "".join([char.get_text().strip() for char in word])
    try:
        strptime(word_text, Config.time_format)
    except ValueError:
        return False
    return True


def get_cells_from_page(page: LTPage) -> tuple[list[C], list[C], list[C]]:
    """ Create an object for each word on the page.

    :param page: A single page of a PDF.
    :type page: LTPage
    :return: Two lists, where the first contains all TimeCells of the page
     and the second contains all Cells not containing a time of the page.
    :rtype: tuple[list[DataField], list[C]]
    """
    text_lines = collapse(page, base_type=LTTextLine)
    words = flatten(map(split_line_into_words, text_lines))
    page_height = page.y1
    cells = map(lambda chars: Cell.from_lt_chars(chars, page_height), words)
    # Remove Cells that do not contain any text.
    cells = filter(lambda f: f.text, cells)
    # Split the cells based on their type.
    non_time_cells, time_cells = partition(
        lambda c: c.has_type(T.Time, strict=True), cells)
    # Some text may not have been read properly by pdfminer.
    non_time_cells, invalid_cells = partition(
        lambda c: c.text.startswith("(cid"), non_time_cells)

    # TODO: Add alternative_pre_merge to enable/disable this.
    # non_time_cells = merge_other_cells(non_time_cells)

    return list(time_cells), list(non_time_cells), list(invalid_cells)


def assign_other_cells_to_tables(tables: list[Table], cells: Cs) -> None:
    """ Assign those cells to each table that can be used to expand.

    A cell C can be used to expand a table T1, if no other table T2
    is between C and T1.

    :param tables: All tables of the page.
    :param cells: All cells of the page, that are neither
     TimeCells nor RepeatCells.
    """
    def get_next_lower(sorted_tables: list[Table], axis: str) -> float | None:
        """ Return the upper bound of the next lower table, if it exists.

        Lower means either left or above of the current table.

        :param sorted_tables: The tables sorted beforehand, based on axis.
        :param axis: The axis used to determine whether a table is
            lower or not. Either 'x' or 'y'.
        :return: The upper bound of the next lower table, if it exists.
            Otherwise, None.
        """
        idx = sorted_tables.index(table)
        if idx == 0:
            return None
        getter1 = attrgetter(f"bbox.{axis}1")
        getter2 = attrgetter(f"bbox.{axis}0")
        lower = first_true(sorted_tables[idx - 1::-1],
                           pred=lambda t: getter1(t) < getter2(table))
        return cast(float, getter1(lower)) if lower else None

    def get_next_upper(sorted_tables: list[Table], axis: str) -> float | None:
        """ Return the lower bound of the next upper table, if it exists.

        Upper means either right or below of the current table.

        :param sorted_tables: The tables sorted beforehand, based on axis.
        :param axis: The axis used to determine whether a table is
            upper or not. Either 'x' or 'y'.
        :return: The lower bound of the next upper table, if it exists.
            Otherwise, None.
        """
        idx = sorted_tables.index(table)
        if idx == len(sorted_tables) - 1:
            return None
        getter1 = attrgetter(f"bbox.{axis}0")
        getter2 = attrgetter(f"bbox.{axis}1")
        upper = first_true(
            sorted_tables[idx + 1:],
            pred=lambda t: getter1(t) > getter2(table))
        return cast(float, getter1(upper)) if upper else None

    tables_y0 = sorted(tables, key=attrgetter("bbox.y0"))
    tables_y1 = sorted(tables, key=attrgetter("bbox.y1"))
    tables_x0 = sorted(tables, key=attrgetter("bbox.x0"))
    tables_x1 = sorted(tables, key=attrgetter("bbox.x1"))
    for table in tables:
        t_above = get_next_lower(tables_y0, "y")
        t_below = get_next_upper(tables_y1, "y")
        t_prev = get_next_lower(tables_x0, "x")
        t_next = get_next_upper(tables_x1, "x")
        bounds = Bounds(t_above, t_prev, t_below, t_next)
        table.potential_cells = [f.duplicate() for f in cells
                                 if bounds.within_bounds(f)]


def create_tables_from_page(page: LTPage) -> list[Table]:
    """ Use the cells on the page to create the tables.

    :param page: An LTPage.
    :return: A list of tables, where each table is minimal in the sense
        that it can not be easily split into multiple tables where each
        table still contains a stop col/row; they are also maximal, in
        the sense that no other cells exist on the page, that can be
        attributed to the table in a simple manner.
    """
    time_cells, non_time_cells, invalid_cells = get_cells_from_page(page)
    t = Table.from_time_cells(time_cells)
    other_cells = non_time_cells
    t.insert_repeat_cells(other_cells)
    t.print(None)
    tables = t.max_split(other_cells)
    assign_other_cells_to_tables(tables, other_cells)
    for t in tables:
        t.expand_all()
        logger.info("Found the following table:")
        t.print(None)
        t.cleanup(tables[0] if t != tables[0] else None)
        logger.info("With the following types:")
        t.print_types()
    if Config.merge_split_tables:
        tables = merge_tables(tables)
    return tables


def tables_to_timetables(tables: list[Table]) -> list[TimeTable]:
    timetables = []
    for table in tables:
        timetable = table.to_timetable()
        if not timetable:
            continue
        timetables.append(timetable)
    return timetables


def sniff_page_count(file: str | Path) -> int:
    """ Return the number of pages in the given PDF. """

    with open(file, "rb") as file:
        parser = PDFParser(file)
        document = PDFDocument(parser)
        page_count = document.catalog["Pages"].resolve()["Count"]
    return page_count


def get_pages(file: str | Path) -> Iterator[LTPage]:
    """ Return the lazy iterator over the selected pages. """
    # Disable advanced layout analysis.
    laparams = LAParams(boxes_flow=None, all_texts=True)
    return extract_pages(
        file, laparams=laparams, page_numbers=Config.pages.page_ids)


def split_line_into_fields(line: Line) -> list[PDFField]:
    """ Split the given chars into fields,
    merging multiple fields, based on their x coordinates. """
    fields = []
    if len(line) == 0:
        return fields

    # Fields are semi-continuous streams of chars. May not be strictly
    #  continuous, because we rounded the coordinates.
    for char in sorted(line, key=attrgetter("x0")):
        char_field = PDFField.from_char(char)
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
    pdf_tables = []
    for table in cleanup_tables(split_rows_into_tables(rows)):
        if table.empty:
            continue
        table.fix_split_stopnames()
        pdf_tables.append(table)
    return pdf_tables


def pdf_tables_to_timetables(pdf_tables: list[PDFTable]) -> list[TimeTable]:
    """ Create TimeTables using the PDFTables"""
    timetables = []
    for table in pdf_tables:
        timetable = table.to_timetable()
        timetables.append(timetable)
    return timetables


def tables_to_csv(page_id: int, tables: list[Table] | list[PDFTable]) -> None:
    """ Export the given tables to the temporary directory as .csv files.

    :param page_id: The page_id of the page the tables come from.
    :param tables: The tables we want to export.
    """
    page = Config.pages.page_num(page_id)
    input_name = Path(Config.filename).stem
    logger.info(f"Writing tables of page {page} "
                f"as .csv to {Config.temp_dir}...")
    for table_id, table in enumerate(tables, 1):
        legacy = "-legacy" if Config.use_legacy_extraction else ""
        fname = f"{page:02}-{table_id:02}{legacy}-{input_name}.csv"
        path = Config.output_dir.joinpath(fname)
        table.to_file(path)


def page_to_timetables(page: LTPage) -> list[TimeTable]:
    """ Extract all timetables from the given page. """
    if Config.use_legacy_extraction:
        logger.info("Using legacy extraction algorithm.")
        char_df = get_chars_dataframe(page)
        pdf_tables = get_pdf_tables_from_df(char_df)
        tables_to_csv(page.pageid, pdf_tables)
        time_tables = pdf_tables_to_timetables(pdf_tables)
    else:
        cell_tables = create_tables_from_page(page)
        tables_to_csv(page.pageid, cell_tables)
        time_tables = tables_to_timetables(cell_tables)

    logger.info(f"Number of tables found: {len(time_tables)}")
    return time_tables


def preprocess_check() -> bool:
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
        if not preprocess_check():
            return

        from ghostscript import Ghostscript, GhostscriptError

        logger.info("Beginning preprocessing...")
        start = time()
        prefix = f"p2g_preprocess_{self.filepath.stem}_"
        self.tempfile = NamedTemporaryFile(
            delete=False, prefix=prefix, suffix=".pdf")
        # GS can't use an open file as outfile (maybe system dependent).
        self.tempfile.close()

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
        try:
            count = sniff_page_count(self.filepath)
        except (OSError, PermissionError, PDFSyntaxError):
            logger.error("Could not determine number of pages. Is this PDF "
                         "valid and readable?")
            sys.exit(PDF_READ_ERROR_CODE)
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
                        f"{time() - start:.2f} seconds.")
            timetables += page_to_timetables(page)
            start = time()

        return timetables
