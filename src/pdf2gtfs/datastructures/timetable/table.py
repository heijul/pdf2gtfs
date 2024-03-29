""" TimeTable, created using PDFTable and used to create the GTFS files. """

from __future__ import annotations

import logging

import pdf2gtfs.datastructures.pdftable.pdftable as pdftable
from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.pdftable.enums import ColumnType
from pdf2gtfs.datastructures.timetable.entries import (
    TimeTableEntry, TimeTableRepeatEntry)
from pdf2gtfs.datastructures.timetable.stops import Stop, StopList


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

        table = TimeTable()

        for raw_column in list(pdf_table.columns):
            if raw_column.type == ColumnType.OTHER:
                continue
            entry = get_entry(raw_column)
            table.entries.append(entry)
            process_raw_column(table, raw_column)
            # Remove entries, in case raw_column is empty.
            if not table.entries[-1].values:
                del table.entries[-1]

        if Config.min_connection_count > 0:
            table.detect_connection()
        return table


def get_entry(raw_column: pdftable.Column) -> TimeTableEntry:
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

    header_text = raw_column.table.get_header_from_column(raw_column)
    if raw_column.type == ColumnType.REPEAT:
        entry = TimeTableRepeatEntry(
            header_text, raw_column.get_repeat_intervals())
    else:
        entry = TimeTableEntry(header_text)
    entry.annotations = get_annotations(raw_column)
    entry.route_name = get_route_name(raw_column)
    return entry


def process_raw_column(table: TimeTable, raw_column: pdftable.Column) -> None:
    """ Updates the table, based on the type of the column and the type of
    each column fields' row.
    """
    for raw_field in raw_column:
        row_id = raw_field.row.index
        # Only add stops for fields of stop columns where the row contains data
        if raw_field.column.type == ColumnType.STOP:
            if raw_field.row.type == pdftable.RowType.DATA:
                stop = Stop(raw_field.text, row_id)
                table.stops.add_stop(stop)
            continue
        if raw_field.row.type in [pdftable.RowType.ROUTE_INFO,
                                  pdftable.RowType.ANNOTATION]:
            continue
        if raw_field.column.type == ColumnType.STOP_ANNOTATION:
            table.stops.add_annotation(raw_field.text, stop_id=row_id)
        elif raw_field.row.type == pdftable.RowType.DATA:
            stop = table.stops.get_from_id(row_id)
            table.entries[-1].set_value(stop, raw_field.text)
