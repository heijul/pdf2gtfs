from __future__ import annotations

import logging

import datastructures.rawtable.table as raw
from datastructures.rawtable.enums import ColumnType
from datastructures.timetable.entries import TimeTableEntry
from datastructures.timetable.stops import Stop


logger = logging.getLogger(__name__)


class StopList:
    def __init__(self):
        self._stops: list[Stop] = []

    @property
    def all_stops(self):
        return self._stops

    @property
    def stops(self):
        return [stop for stop in self._stops if not stop.is_connection]

    def add_stop(self, stop: Stop) -> None:
        self._stops.append(stop)

    def get_from_id(self, row_id: int):
        for stop in self.stops:
            if stop.raw_row_id == row_id:
                return stop

    def add_annotation(self, text: str,
                       *, stop: Stop = None, stop_id: int = None) -> None:
        if stop_id is not None:
            stop = self.get_from_id(stop_id)
        stop.annotation = text

    def clean(self):
        for stop in self._stops:
            stop.clean()


class TimeTable:
    def __init__(self):
        self.stops = StopList()
        self.entries: list[TimeTableEntry()] = []

    def detect_connection(self):
        """ Detect stops which are actually connections.

        Will search for reoccurring stops and mark every stop within the
        cycle as a connection. Stops with different arrival/departure times
        will not be added as connections because of how range works.
        """

        cycles: dict[str, list[int]] = {}
        for i, stop in enumerate(self.stops.all_stops):
            cycle = cycles.setdefault(stop.name, [])
            cycle.append(i)

        indices = []
        for cycle in cycles.values():
            if len(cycle) == 1:
                continue
            start_idx = sorted(cycle)[0] + 1
            end_idx = sorted(cycle)[-1]

            # Prevent marking every stop as connection if it's a round trip.
            if start_idx == 0 and end_idx == len(self.stops.stops) - 1:
                continue
            indices += list(range(start_idx, end_idx))
            for stop in self.stops.all_stops[start_idx:end_idx]:
                stop.is_connection = True

    @staticmethod
    def from_raw_table(raw_table: raw.Table) -> TimeTable:
        table = TimeTable()

        for raw_column in list(raw_table.columns):
            raw_header_text = raw_table.get_header_from_column(raw_column)
            table.entries.append(TimeTableEntry(raw_header_text))

            for raw_field in raw_column:
                row_id = raw_table.rows.index(raw_field.row)
                if raw_field.column.type == ColumnType.STOP:
                    if raw_field.row.type == raw.RowType.DATA:
                        stop = Stop(raw_field.text, row_id)
                        table.stops.add_stop(stop)
                    continue
                if raw_field.column.type == ColumnType.STOP_ANNOTATION:
                    table.stops.add_annotation(raw_field.text, stop_id=row_id)
                elif raw_field.row.type == raw.RowType.ANNOTATION:
                    # Ignore row annotations for now.
                    # TODO: Implement this.
                    pass
                elif raw_field.row.type == raw.RowType.DATA:
                    stop = table.stops.get_from_id(row_id)
                    table.entries[-1].set_value(stop, raw_field.text)
            # TODO: Check why this happens and fix it.
            if not table.entries[-1].values:
                del table.entries[-1]

        table.detect_connection()
        if table.stops.stops:
            logger.info(table)
        return table

    def clean_values(self):
        self.stops.clean()

    def __str__(self):
        # Entry columns + stop column
        base_text = "{:30}" + "{:>6}" * len(self.entries)
        texts = []
        for stop in self.stops.stops:
            text = [str(stop)]
            for entry in self.entries:
                value = entry.get_value(stop)
                text.append(value if value else "-")
            texts.append(base_text.format(*text).strip())
        return "TimeTable:\n\t" + "\n\t".join(texts)
