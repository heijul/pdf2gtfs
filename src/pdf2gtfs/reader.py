""" Used to read the pdf file. """

import logging
import os
import sys
from operator import attrgetter
from pathlib import Path
from shutil import copyfile
from statistics import mean
from tempfile import NamedTemporaryFile
from time import strptime, time
from typing import Iterator, Optional, Tuple, TypeAlias, Union

import pandas as pd
from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTChar, LTPage, LTTextBox, LTTextLine
from pdfminer.pdfcolor import PDFColorSpace
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdffont import PDFFont
from pdfminer.pdfinterp import PDFGraphicState
from pdfminer.pdfparser import PDFParser, PDFSyntaxError
from pdfminer.utils import Matrix

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.pdftable import Char
from pdf2gtfs.datastructures.pdftable.datafields import (
    DataField, TableFactory, TableField)
from pdf2gtfs.datastructures.pdftable.field import Field
from pdf2gtfs.datastructures.pdftable.pdftable import (
    cleanup_tables, PDFTable, Row, split_rows_into_tables)
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
    except TypeError:
        logger.debug("Encountered charcode '{text}' with length "
                     "{len(text)}, but could not convert it to char.")


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

        Rounds the coordinates and drops any entries outside of the page.
        """
        # Round to combat possible tolerances in the coordinates.
        df = df.round({"x0": 2, "x1": 2, "y0": 2, "y1": 2})
        # Skip objects which are not on the page.
        return df[(df["x0"] < df["x1"]) & (df["y0"] < df["y1"]) &
                  (df["x0"] >= page.x0) & (df["x1"] <= page.x1) &
                  (df["y0"] >= page.y0) & (df["y1"] <= page.y1)]

    char_list = []
    text_boxes = [box for box in page if isinstance(box, LTTextBox)]
    text_lines = [line for text_box in text_boxes for line in text_box
                  if isinstance(line, LTTextLine)]
    text_chars = [char for line in text_lines for char in line
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
    # Create lists of chars, that each belong to the same word.
    words: list[list[LTChar]] = []
    for char in line:
        not_a_char = not isinstance(char, LTChar)
        if char.get_text() in (" ", "\n") or not words or not_a_char:
            words.append([])
        if not_a_char:
            continue
        words[-1].append(char)
    # Drop empty words.
    return [word for word in words if word]


def get_datafields(line: LTTextLine, height: float
                   ) -> tuple[list[DataField], list[TableField]]:
    words = split_line_into_words(line)
    data_words = []
    other_words = []
    for word in words:
        word_text = "".join([char.get_text() for char in word]).strip()
        try:
            strptime(word_text, Config.time_format)
            data_words.append(word)
        except ValueError:
            other_words.append(word)
            continue

    fields = [DataField(chars=word, page_height=height) for word in data_words]
    other_fields = [TableField(word, height) for word in other_words]
    # Remove fields without text.
    fields = [f for f in fields if f.text]
    other_fields = [f for f in other_fields if f.text]
    return fields, other_fields


def merge_other_fields(fields: list[TableField]) -> list[TableField]:
    # Split fields into rows, using the respective vertical overlap.
    fields = sorted(fields, key=attrgetter("bbox.y0", "bbox.x0"))
    rows = []
    row = [fields[0]]
    for field in fields[1:]:
        if not row[0].bbox.is_v_overlap(field.bbox, 0.9):
            rows.append(row)
            row = []
        row.append(field)
    rows.append(row)
    merged_fields = []
    for row in rows:
        row = sorted(row, key=attrgetter("bbox.x0"))
        prev = row[0]
        for field in row[1:]:
            # Fields of different fonts indicate different meaning.
            other_font = (prev.fontsize != field.fontsize
                          and prev.font.fontname != field.font.fontname)
            space_width = prev.font.string_width(" ".encode()) * 1.25
            space_width *= prev.fontsize
            if other_font or abs(prev.bbox.x1 - field.bbox.x0) > space_width:
                merged_fields.append(prev)
                prev = field
                continue
            # Actual merging (BBox, text,
            prev.bbox.merge(field.bbox)
            prev.chars += field.chars
            prev.text += f" {field.text}"
        merged_fields.append(prev)
    return merged_fields


def create_table_factory_from_page(page: LTPage) -> TableFactory:
    text_boxes = [box for box in page if isinstance(box, LTTextBox)]
    text_lines = [line for text_box in text_boxes for line in text_box
                  if isinstance(line, LTTextLine)]
    data_fields = []
    other_fields = []
    for line in text_lines:
        new_fields = get_datafields(line, page.y1)
        data_fields += new_fields[0]
        other_fields += new_fields[1]
    # Merge words of non-data fields
    other_fields = merge_other_fields(other_fields)
    factory = TableFactory.from_datafields(data_fields)
    factory.grow_west(other_fields)
    factory.grow_east(other_fields)
    factory.grow_north(other_fields)
    factory.grow_south(other_fields)
    factory.get_contained_fields(other_fields)
    return factory


def get_pdf_tables_from_datafields(datafields: TableFactory) -> list[PDFTable]:
    pass
    return []


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


def fields_to_rows(fields: list[Field]) -> list[Row]:
    start = time()

    y0 = 0
    fields_rows = []
    max_distance = mean([f.bbox.y1 - f.bbox.y0 for f in fields]) / 2
    for field in sorted(fields, key=attrgetter("bbox.y0")):
        if not field.text:
            continue
        new_line = abs(field.bbox.y0 - y0) > max_distance or not fields_rows
        if new_line:
            y0 = field.bbox.y0
            fields_rows.append([])
        fields_rows[-1].append(field)
    rows = []
    for fields_row in fields_rows:
        rows.append(Row.from_fields(fields_row))

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
        timetable = table.to_timetable()
        timetables.append(timetable)
    return timetables


def page_to_timetables(
        page: LTPage,
        use_datafields: bool = True,
        ) -> list[TimeTable]:
    """ Extract all timetables from the given page. """
    if use_datafields:
        datafields = create_table_factory_from_page(page)
        pdf_tables = get_pdf_tables_from_datafields(datafields)
    else:
        char_df = get_chars_dataframe(page)
        pdf_tables = get_pdf_tables_from_df(char_df)
    tables = pdf_tables_to_timetables(pdf_tables)

    logger.info(f"Number of tables found: {len(tables)}")
    return tables


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
        # GS can't use open files as outfiles (may be system dependent).
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
