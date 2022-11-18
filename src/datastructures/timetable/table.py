""" TimeTable, created using PDFTable and used to create the GTFS files. """

from __future__ import annotations

import logging
from typing import cast

from tabulate import tabulate

import datastructures.pdftable.pdftable as pdftable
from config import Config
from datastructures.pdftable.enums import ColumnType
from datastructures.timetable.entries import (
    TimeTableEntry, TimeTableRepeatEntry, Weekdays)
from datastructures.timetable.stops import DummyAnnotationStop, Stop, StopList


logger = logging.getLogger(__name__)


class TimeTable:
    """ The TimeTable. Provides methods used directly by the GTFSHandler.
     Higher level of abstraction, compared to the PDFTable. """

    def __init__(self) -> None:
        self.stops = StopList()
        self.entries: list[TimeTableEntry] = []

    def detect_connection(self) -> None:
        """ Detect stops which are actually connections.

        Will search for reoccurring stops and mark every stop within the
        cycle as a connection. Stops with different arrival/departure times
        will not be added as connections because of how range works.
        """

        stops = self.stops.all_stops
        cycles: dict[str, list[int]] = {}
        for i, stop in enumerate(stops):
            cycle = cycles.setdefault(stop.name, [])
            cycle.append(i)

        for cycle in cycles.values():
            # Stop only occurs once.
            if len(cycle) == 1:
                continue
            start_idx = cycle[0] + 1
            end_idx = cycle[-1]

            indices = list(range(start_idx, end_idx))
            route_is_round_trip = cycle[0] == 0 and end_idx == len(stops) - 1
            cycle_is_too_short = len(indices) < Config.min_connection_count
            if route_is_round_trip or cycle_is_too_short:
                continue

            for stop in stops[start_idx:end_idx]:
                stop.is_connection = True

    @staticmethod
    def from_pdf_table(pdf_table: pdftable.PDFTable) -> TimeTable:
        """ Creates a new TimeTable, given the pdttable. """

        def get_annotations(column: pdftable.Column):
            """ Return all annotations of the given columns. """
            _annots = set()
            for field in column.fields:
                if field.row.type != pdftable.RowType.ANNOTATION:
                    continue
                # Splitting in case field has multiple annotations
                _annots |= set(field.text.strip().split(" "))
            return {a for a in _annots if a}

        def get_route_name(column: pdftable.Column):
            """ Return the route_name of the given column. """
            for field in column.fields:
                if field.row.type != pdftable.RowType.ROUTE_INFO:
                    continue
                return field.text
            return ""

        table = TimeTable()

        for raw_column in list(pdf_table.columns):
            if raw_column.type == ColumnType.OTHER:
                continue
            raw_header_text = pdf_table.get_header_from_column(raw_column)
            if raw_column.type == ColumnType.REPEAT:
                entry = TimeTableRepeatEntry(
                    raw_header_text, raw_column.get_repeat_intervals())
            else:
                entry = TimeTableEntry(raw_header_text)
            entry.annotations = get_annotations(raw_column)
            entry.route_name = get_route_name(raw_column)
            table.entries.append(entry)

            for raw_field in raw_column:
                row_id = pdf_table.rows.index(raw_field.row)
                if raw_field.column.type == ColumnType.STOP:
                    if raw_field.row.type == pdftable.RowType.DATA:
                        stop = Stop(raw_field.text, row_id)
                        table.stops.add_stop(stop)
                    continue
                if raw_field.row.type == pdftable.RowType.ROUTE_INFO:
                    continue
                if raw_field.row.type == pdftable.RowType.ANNOTATION:
                    continue
                if raw_field.column.type == ColumnType.STOP_ANNOTATION:
                    table.stops.add_annotation(raw_field.text, stop_id=row_id)
                elif raw_field.row.type == pdftable.RowType.DATA:
                    stop = table.stops.get_from_id(row_id)
                    table.entries[-1].set_value(stop, raw_field.text)
            # Remove entries, in case raw_column is empty.
            if not table.entries[-1].values:
                del table.entries[-1]

        if Config.min_connection_count > 0:
            table.detect_connection()
        if table.stops.stops:
            table.print()
        return table

    def print(self) -> None:
        """ Pretty print the table."""

        def days_to_header_values(days: Weekdays) -> str:
            """ Turn the Weekdays to their human-readable form. """
            for key in Config.header_values:
                if str(Weekdays(key)) == str(days):
                    return key
            return ""

        def get_headers() -> list[str]:
            """ Return the headers of the table. """
            headers = ["Days\nRoute\nRoute information"]
            for e in self.entries:
                header = days_to_header_values(e.days).capitalize()
                annot = " ".join(e.annotations) if e.annotations else ""
                headers.append(f"{header}\n{e.route_name}\n{annot}")
            return headers

        rows: list[list[str]] = [[] for _ in range(len(self.stops.stops))]

        for stop, row in zip(self.stops.stops, rows, strict=True):
            row.append(stop.name)
            for entry in self.entries:
                val = entry.get_value(stop)
                row.append(val if val else "–")

        # TODO: Use pd.DataFrame for multicolumn header
        tabulated_table = tabulate(rows, headers=get_headers())
        logger.info("\n" + str(tabulated_table))

    def clean_values(self) -> None:
        """ Clean all stops. """
        self.stops.clean()

    def __str__(self) -> str:
        # Entry columns + stop column
        base_text = "{:30}" + "{:>6}" * len(self.entries)
        texts = []
        for stop in [cast(Stop, DummyAnnotationStop())] + self.stops.stops:
            text = [str(stop)]
            for entry in self.entries:
                if isinstance(stop, DummyAnnotationStop):
                    value = "".join(sorted(entry.annotations))
                else:
                    value = entry.get_value(stop)
                text.append(value if value else "-")
            texts.append(base_text.format(*text).strip())
        return "TimeTable:\n\t" + "\n\t".join(texts)
