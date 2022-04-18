import re
from abc import ABC, abstractmethod
from io import StringIO
from pathlib import Path
from typing import ClassVar

import pandas as pd
import pdfplumber as pdfplumber
import pdftotext
import tabula
import camelot
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser

from datastructures.base import Row, field_from_char, table_from_rows
from datastructures.timetable import TimeTable


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


class ReaderCamelot(BaseReader, ABC):
    tables = []

    def read(self):
        self.tables = camelot.read_pdf(
            str(self.filepath), pages="1", flavor="stream",
            )
        self.tables.export(str(self.out_path) + "_cam.csv", f="csv")


class ReaderTabula(BaseReader, ABC):
    tables: list[pd.DataFrame] = []

    def __init__(self, filename: str = None):
        super().__init__(filename)

    def read(self) -> None:
        raw_tables = tabula.read_pdf(
            self.filepath, pages="1", lattice=True,
            pandas_options={"header": None}
            )
        print(raw_tables)

        #pd.DataFrame(raw_tables[-1]).to_csv("vag_eins_tabula_df.csv")
        #pd.DataFrame(raw_tables[-1]).to_csv("rmv_u1_tabula_df.csv")
        pd.DataFrame(raw_tables[-1]).to_csv("rmv_u1_pdfact_tabula_df.csv")

        self.tables = self.split_tables(raw_tables)
        self.clean_tables()
        self.remerge_tables()

    def split_tables(self, raw_tables: list[pd.DataFrame]) -> None:
        tables: list[list] = []

        for table in raw_tables:
            table = TimeTable(table)
            continue
            for line in table:
                if line[0].isna():
                    tables.append([])
                tables[-1].append(line)

        self.tables = [pd.DataFrame(table) for table in tables]


    def clean_tables(self):
        ...

    def remerge_tables(self):
        ...


class ReaderXPDF(BaseReader, ABC):
    tables: list = []

    def __init__(self, filename: str = None):
        if not filename:
            filename = "./data/vag_linie_eins_p1.txt"
        super().__init__(filename)

    def read(self):
        with open(self.filepath) as fil:
            file_content = fil.read()
        self.read_csv(file_content)

    def read_csv_pandas(self):
        data = pd.read_csv(
            self.filepath, delim_whitespace=True, verbose=True, header=None,
            engine="python", on_bad_lines=self.errr)
        print(data)

    @staticmethod
    def errr(bad_line):
        print(bad_line)

    def replace_long_whitespace_with_tab(self, line: str):
        # Replaces all whitespace of length greater than 1 with a tab.
        return re.sub("  +", "\t", line)

    def cleanup_whitespace(self, file_content):
        # Changes the content to use tab as a separator instead.
        # Remove leading/trailing whitespace and empty lines.
        clean: list[str] = []
        for line in file_content.split("\n"):
            if not line.strip():
                continue
            line = self.replace_long_whitespace_with_tab(line.strip())
            clean.append(line)
        return clean

    def read_csv(self, file_content):
        # Split tables in case there are multiple in the file.
        wrapped_extra_info: dict[int, list] = {}
        delim = "\t"
        tables: list[list[list[str]]] = [[]]
        for line in self.cleanup_whitespace(file_content):
            fields = [field for field in line.split(delim)]
            # Outside the table.
            if not str(fields[0]).strip() or fields[0][0].isnumeric():
                if tables[-1]:
                    tables.append([])
                wrapped_extra_info[len(tables) - 1] = fields
                continue
            tables[-1].append(fields)
        print(tables)
        self.transform_(tables[0][:5])

    def transform_(self, table: list):
        timetable: list = []
        for line in table:
            line = [field.strip() for field in line]
            # Skip the first fields, until we find a time
            i: int = 0
            for i, field in enumerate(line):
                if field and field[0].isnumeric():
                    break
            if i + 1 == len(line):
                continue
            timetable.append((i, line[i:]))
        print(timetable)

    def transform(self):
        pass


class Reader(BaseReader, ABC):
    def read(self):
        pdfminer_string = StringIO()
        with open(self.filepath, "rb") as in_file:
            parser = PDFParser(in_file)
            doc = PDFDocument(parser)
            rsrcmgr = PDFResourceManager()
            device = TextConverter(rsrcmgr,
                                   pdfminer_string,
                                   laparams=LAParams())
            interpreter = PDFPageInterpreter(rsrcmgr, device)
            interpreter.process_page(next(PDFPage.create_pages(doc)))
            #for page in PDFPage.create_pages(doc):
            #    interpreter.process_page(page)
        pdfminer_lines = pdfminer_string.getvalue().splitlines()
        pdfminer_lines = [ln for ln in pdfminer_lines if ln]

    def read2(self):
        with open(self.filepath, 'rb') as file:
            pdftotext_string = pdftotext.PDF(file, raw=True)
        pdftotext_lines = ("\n\n".join(pdftotext_string).splitlines())
        pdftotext_lines = [ln for ln in pdftotext_lines if ln]

    def read3(self):
        with open(self.filepath, "rb") as file:
            q = pdfplumber.PDF(file)
            csv_io = StringIO(q.pages[0].to_csv())

        # Read csv with pandas.
        w = pd.read_csv(csv_io)
        df = self.clean_df(w)
        # df.to_csv("./testtest.csv")
        self.get_lines(df)

    def read4(self):
        table_settings = {"vertical_strategy": "text",
                          "horizontal_strategy": "text"}
        pdf = pdfplumber.open(self.filepath)
        tables = pdf.pages[0].extract_tables(table_settings)
        print(len(tables))

    def clean_df(self, df: pd.DataFrame):
        # Maybe: doctop/top, width, height, adv, fontname, size, upright
        columns = ["page_number", "x0", "x1", "y0", "y1", "top", "width", "height", "text", "upright"]
        # Remove lines/curves/rects
        df = df.where(df["object_type"] == "char").dropna(how="all")
        # Only select necessary columns.
        return df.reset_index()[columns]

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
    reader = ""
    if reader == "":
        r_custom = Reader(fnames[0])
        r_custom.read3()
    elif reader == "tab":
        r_tab = ReaderTabula(fnames[2])
        r_tab.read()
    else:
        r_cam = ReaderCamelot(fnames[1])
        r_cam.read()
