""" The new Table, that is able to detect Tables regardless of Orientation. """
from __future__ import annotations

import logging
from itertools import pairwise
from operator import attrgetter, methodcaller
from pathlib import Path
from typing import Callable, Iterable, Iterator, TYPE_CHECKING

from more_itertools import (
    always_iterable, collapse, first_true, peekable, split_when,
    )

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.pdftable.bbox import BBox
from pdf2gtfs.datastructures.table.bounds import select_adjacent_cells
from pdf2gtfs.datastructures.table.cell import (
    Cell, EmptyCell, C, Cs, OC,
    )
from pdf2gtfs.datastructures.table.celltype import T
from pdf2gtfs.datastructures.table.direction import (
    D, Direction, E, H, N, Orientation, S, V, W,
    )


if TYPE_CHECKING:
    from pdf2gtfs.datastructures.timetable.table import TimeTable


logger = logging.getLogger(__name__)


def merge_series(starter: C, d: Direction) -> None:
    """ Merge the row/col of the given Cell to the neighboring series.

    :param starter: Used to get the series in the Direction's
        default Orientation's normal Orientation.
    :param d: The Cells row/col will be merged with
        their respective neighbors in this Direction.
    """
    neighbor = starter.get_neighbor(d)
    if not neighbor:
        raise AssertionError(f"Can't merge in {d.name}. End of Table.")
    normal = d.o.normal
    series = list(starter.iter(o=normal))
    neighbors = list(neighbor.iter(o=normal))
    for f1, f2 in zip(series, neighbors, strict=True):
        f1.merge(f2, ignore_neighbors=[normal.lower, normal.upper])


class Table:
    """ Table using Cells linked in all four Directions (= QuadLinkedList).
    Able to expand in all Directions using adjacent Cells.
    """
    def __init__(self, first_cell: C, last_cell: C):
        self.bboxes: dict[int: int] = {}
        self._left = None
        self._right = None
        self._top = None
        self._bot = None
        self._update_end(W, first_cell)
        self._update_end(E, last_cell)
        self._update_end(N, first_cell)
        self._update_end(S, last_cell)
        # Set self as Table on all Cells.
        for row_cell in self.top.row:
            for col_cell in row_cell.col:
                col_cell.table = self
        self.potential_cells = None

    @property
    def top(self) -> OC:
        """ The left-most Cell in the top row. This is equal to left. """
        return self.get_end(d=N)

    @property
    def left(self) -> OC:
        """ The top Cell in the first column. This is equal to top. """
        return self.get_end(d=W)

    @property
    def bot(self) -> OC:
        """ The right-most Cell in the bottom row. This is equal to right. """
        return self.get_end(d=S)

    @property
    def right(self) -> OC:
        """ The bottom Cell in the last column. This is equal to bot. """
        return self.get_end(d=E)

    @property
    def bbox(self) -> BBox:
        """ The BBox that contains every Cell of the Table. """
        return self.get_bbox_of(collapse((self.left.col, self.top.row,
                                          self.right.col, self.bot.row)))

    @staticmethod
    def from_time_cells(time_cells: Cs) -> Table:
        """ Create a new Table from the given TimeCells.

        :param time_cells: The Cells of Type Time used to construct the Table.
        :return: A new Table containing all the given Cells.
        """
        cols = cells_to_cols(time_cells)
        rows = cells_to_rows(time_cells)
        cols, rows = link_rows_and_cols(rows, cols)
        t = Table(cols[0][0], rows[-1][-1])
        return t

    def get_end(self, d: Direction) -> OC:
        """ Return one of the end Cells in the given Direction.

        :param d: The Direction to look for the end Cell in.
        """
        # Get the current end Cell.
        cell: OC = getattr(self, d.p_end)
        # Need to update the end Cell, because it is not a proper end Cell.
        if cell.has_neighbors(d=d) or cell.has_neighbors(d=d.normal_eqivalent):
            self._update_end(d, cell)
            return self.get_end(d)
        return cell

    def _set_end(self, d: Direction, cell: OC) -> None:
        """ Store the given Cell as the last Cell in the given Direction.

        This will fail if the Cell has a neighbor in the given Direction.

        :param d: The Direction, which specifies where to store the Cell.
        :param cell: The Cell to be stored.
        """
        assert cell.get_neighbor(d) is None
        setattr(self, d.p_end, cell)

    def _update_end(self, d: Direction, start: C) -> None:
        """ Update the end Cell in the given Direction
        to the farthest/last Cell in that Direction.

        Always ensures that the end Cell in the lower Direction of one
        Orientation is also the end Cell in the lower Direction of the
        other Orientation.
        That is, if d is N (i.e., V.lower), the end Cell is the same as it
        would be, if d were W (i.e., H.lower). Analogous for S/E.

        :param d: The Direction to look for the last Cell.
        :param start: The Cell to use to start looking for the end Cell in d.
        """
        self._set_end(d, start.get_last(d).get_last(d.normal_eqivalent))

    def insert(self, d: Direction, rel_cell: OC, new_cell: C) -> None:
        """ Inserts new_cell relative to the rel_cell in the given Direction.

        :param d: The relative Direction of Cell to rel_cell, after insertion.
        :param rel_cell: Either a Cell or None.
            If it is a Cell, insert new_cell adjacent to it.
            If it is None, insert new_cell as the last Cell in d.
        :param new_cell: The Cell that will be inserted.
        """
        normal = d.o.normal

        new_cells = list(new_cell.iter(o=normal))
        # Check that each new_cell only has neighbors that are in new_cells.
        # Otherwise, bad things may happen.
        for cell in new_cells:
            for neighbor in cell.get_neighbors(allow_none=False):
                assert neighbor in new_cells
        # If we want to insert a column (i.e., vertical) at the beginning/end,
        # we need a row (i.e., horizontal) to get the first/last column.
        if rel_cell is None:
            rel_cell = self.get_end(normal.lower)
        rel_cells = list(rel_cell.iter(o=normal))

        # Strict, to ensure the same number of Cells.
        for rel_cell, new_cell in zip(rel_cells, new_cells, strict=True):
            rel_cell.set_neighbor(d, new_cell)
            new_cell.table = self

    def get_bbox_of(self, cells: Iterator[C]) -> BBox:
        """ Return the combined BBox of the given Cells.

        Also caches the results in case the same BBox is requested again,
        using the hash of the Cells bboxes.

        :param cells: The Cells to get the BBox from.
        :return: A BBox that contains all the Cells' bboxes.
        """
        bboxes = [c.bbox for c in cells if not isinstance(c, EmptyCell)]
        # No need to cache a single BBox.
        if len(bboxes) == 1:
            return bboxes[0]
        # If a BBoxes' coordinates change, its hash changes as well.
        cell_hashes = sorted(map(hash, bboxes))
        cell_hash = hash("".join(map(str, cell_hashes)))
        if cell_hash not in self.bboxes:
            self.bboxes[cell_hash] = BBox.from_bboxes(bboxes)
        return self.bboxes[cell_hash]

    def expand(self, d: Direction) -> bool:
        """ Expand the Table in the given Direction using the given Cells.

        :param d: The Direction the expansion is done towards.
        :return: Whether any Cells were added.
        """

        def merge_cells_of_same_row(cells: Cs) -> None:
            rows: list[list[Cell]] = cells_to_rows(cells, link_rows=False)
            for row in rows:
                for row_cell in row[1:]:
                    row[0].merge(row_cell)
                    adjacent_cells.remove(row_cell)

        if self.potential_cells is None:
            raise Exception("Potential Cells must be added to this Table, "
                            "before trying to expand it.")
        normal = d.o.normal
        ref_cells = list(self.get_end(d).iter(o=normal))

        bboxes = [self.get_bbox_of(f.iter(o=d.o)) for f in ref_cells]
        adjacent_cells = select_adjacent_cells(d, bboxes, self.potential_cells)
        if not adjacent_cells:
            return False

        if d in [W, E]:
            merge_cells_of_same_row(adjacent_cells)
        link_cells(normal.upper, adjacent_cells)
        merge_small_cells(d.o, ref_cells, adjacent_cells)

        head = insert_empty_cells_from_map(
            normal, ref_cells, adjacent_cells)
        try:
            self.insert(d, ref_cells[0], head)
        except ValueError:
            # Insertion has failed. This usually (hopefully) means
            # that the adjacent Cells are not part of the Table.
            unlink_cells(d, ref_cells)
            return False
        # Only remove Cells from the potential cells that were added to self.
        for cell in adjacent_cells:
            self.potential_cells.remove(cell)
        return True

    def expand_all(self) -> None:
        """ Exhaustively expand the Table in the lower Directions (N, W). """
        expanded = True
        while expanded:
            expanded = False
            for d in D:
                if d.name not in Config.table_expansion_directions:
                    continue
                expanded |= self.expand(d)

    def get_contained_cells(self, cells: Cs) -> Cs:
        """ Get all Cells that are within the Table's BBox.

        :param cells: The Cells that might be contained by the Table.
        :return: A list of all Cells of all given Cells that have a BBox
            that is contained in the Tables BBox.
        """
        def _both_overlap(cell: C) -> bool:
            return (self.bbox.is_v_overlap(cell.bbox, 0.8) and
                    self.bbox.is_h_overlap(cell.bbox, 0.8))

        cells = list(filter(_both_overlap, cells))
        return cells

    def get_containing_col(self, cell: C) -> Cs | None:
        """ Find the column that contains the Cell (determined using the BBox).

        :param cell: The Cell we want to know the column of.
        :return: The column that contains the Cell
            or None if no such column exists.
        """
        for col_cell in self.left.iter(E):
            if col_cell.is_overlap(H, cell, 0.8):
                return list(col_cell.col)
        return None

    def get_col_left_of(self, cell: C) -> Cs:
        """ Get the last column left of the Cell.

        That is, the column right of whichever column this function returns
        (if any) either contains the Cell or is located right of the Cell.

        :param cell: The Cell we are using as reference.
        :return: The last column left of the Cell or
            None if no such column exists.
        """
        def _is_right_of_cell(f: C) -> bool:
            return f.bbox.x0 >= left_most_cell.bbox.x0

        if cell.table == self:
            return cell.prev.col

        top_cell = cell
        while top_cell.above:
            top_cell = top_cell.above

        left_most_cell = min(top_cell.iter(S), key=attrgetter("bbox.x0"))
        col_right_of_cell = first_true(
            self.left.row, default=None, pred=_is_right_of_cell)

        if col_right_of_cell is None:
            return []

        return col_right_of_cell.prev.col

    def insert_repeat_cells(self, cells: Cs) -> None:
        """ Find the Cells that are part of a repeat interval
        and add them to the Table.

        :param cells: The Cells that are checked for repeat intervals.
        """
        identifiers = self.get_repeat_identifiers(cells)
        if not identifiers:
            return
        values = self.get_repeat_values(identifiers, cells)
        for cell in identifiers + values:
            cells.remove(cell)
        # Add identifiers and their values to Table.
        # Group repeat Cells by col and link them.
        repeat_groups = cells_to_cols(identifiers + values)
        # Insert the repeat_groups each into a new or existing column.
        for group in repeat_groups:
            col = self.get_containing_col(group[0])
            if col:
                unlink_cells(S, group)
                insert_cells_in_col(col, group)
                continue
            col = list(self.get_col_left_of(group[0]))
            insert_direction = E if col else W
            if not col:
                col = self.left.col
            head = insert_empty_cells_from_map(V, col, group)
            self.insert(insert_direction, col[0], head)

    def get_repeat_identifiers(self, cells: Cs) -> Cs:
        """ Return those Cells that are RepeatIdents.

        :param cells: The Cells that may be RepeatIdents.
        :return: Those Cells that are RepeatIdents.
        """
        contained_cells = self.get_contained_cells(cells)
        repeat_identifiers = [f for f in contained_cells
                              if f.has_type(T.RepeatIdent)]
        if repeat_identifiers:
            cells_to_cols(repeat_identifiers)
        return repeat_identifiers

    def get_repeat_values(self, identifiers: Cs, cells: Cs) -> Cs:
        """ Given the RepeatIdents, find those Cells that are RepeatValues.

        :param identifiers: The RepeatIdents.
        :param cells: The Cells that are evaluated.
        :return: Those Cells that are RepeatValues.
        """
        contained_cells = self.get_contained_cells(cells)
        values = []
        repeat_groups = cells_to_cols(identifiers + values, link_cols=False)
        for group in repeat_groups:
            for i1, i2 in pairwise(group):
                overlaps = [f for f in contained_cells
                            if f.is_overlap(H, i1, 0.8)
                            and f.has_type(T.RepeatValue)]
                # Only a single value is needed/possible.
                for value in overlaps:
                    if i1.bbox.y0 < value.bbox.y0 < i2.bbox.y0:
                        values.append(value)
                        break
        return values

    def _print(self, getter_func: Callable[[C], str],
               align_func: Callable[[C], str] = lambda _: "^",
               col_count: int | None = None) -> None:
        """ Print the Cells of the Table to stdout.

        :param getter_func: A function used to get the value that is printed.
        :param align_func: A function used to align each value.
        :param col_count: The maximum number of columns to print.
        """
        rows = [cell.row for cell in self.left.col]
        cols = [cell.col for cell in self.top.row]
        # The maximum length of a Cell's text in each column.
        col_len = [max(map(len, map(getter_func, col))) for col in cols]

        delim = " | "
        lines = []
        for row in rows:
            values = [f"{getter_func(f): {align_func(f)}{col_len[i]}}"
                      for i, f in enumerate(row)][:col_count]
            lines += [delim.lstrip() + delim.join(values) + delim.rstrip()]

        logger.info("\n" + "\n".join(lines))

    def print(self, col_count: int | None = 8) -> None:
        """ Print the Table to stdout.

        :param col_count: The maximum number of columns that will be printed.
        """
        def get_text_align(c) -> str:
            """ Right align all TimeCells; left align everything else.

            :param c: This Cell's text is checked.
            :return: The format character used for alignment.
            """
            return ">" if c.has_type(T.Time, strict=True) else "<"

        self._print(attrgetter("text"), get_text_align, col_count)

    def print_types(self, col_count: int = None) -> None:
        """ Print the inferred type of each Cell, instead of its text.

        :param col_count: The maximum number of columns that will be printed.
        """
        def _get_type_name(c: C) -> str:
            if isinstance(c, EmptyCell):
                return ""
            return c.get_type().name

        self._print(_get_type_name, col_count=col_count)

    def to_file(self, fname: Path) -> None:
        """ Export the Table to the given Path as .csv file. """
        def wrap_cell_text(cell: Cell) -> str:
            """ Wrap cell text that contains a comma in quotes.

            Also removes any existing quotes.
            """
            if cell.has_type(*bad_types, strict=True):
                return ""
            text = cell.text.replace('"', "")
            if "," in text:
                return f'"{text}"'
            return text

        rows = []
        first_col = list(self.left.col)
        bad_types = (T.Other, T.LegendIdent, T.LegendValue)
        for row_starter in first_col:
            texts = list(map(wrap_cell_text, row_starter.row))
            if not any(texts):
                continue
            rows.append(",".join(texts))
        table_str = "\n".join(rows) + "\n"
        with open(fname, "w") as fil:
            fil.write(table_str)

    def split_at_cells(self, o: Orientation, splitter: list[Cs]
                       ) -> list[Table]:
        """ Split the Table at the given Cells.

        The splitter will not be part of any Table.

        :param o: The Orientation to split the Table in.
        :param splitter: The Cells used to split the Table.
        :return: A list of Tables, where each Table contains only Cells
            that are between the given splitter.
        """

        def _split_at_splitter() -> list[Cs]:
            def _same_table(cell1: C, cell2: C) -> bool:
                return cell1.table != cell2.table

            cells = list(self.get_end(o.lower).iter(o=o.normal))
            cells += list(collapse(splitter))
            pre_sorter = "bbox.y0" if o == H else "bbox.x0"
            return group_cells_by(cells, _same_table, pre_sorter, None)

        if not splitter:
            return [self]
        cell_groups = _split_at_splitter()

        tables = []
        for group in cell_groups:
            head = group[0]
            # The splitter should not implicitly be part of any Table.
            if head.table != self:
                continue
            # Unlink the last row/col of each Table, based on o.
            last_series = list(group[-1].iter(o=o))
            unlink_cells(o.normal.upper, last_series)
            # Create a new Table.
            table = Table(head, last_series[-1])
            table.remove_empty_series()
            tables.append(table)

        return tables

    def _get_splitting_series(self, o: Orientation, grouped_cells: list[Cs]
                              ) -> list[Cs]:
        splitter = []
        idx = 0
        normal = o.normal
        table_cells = list(self.get_end(normal.upper).iter(o=normal))

        bound = normal.lower.coordinate
        for group in grouped_cells:
            group_bbox = BBox.from_bboxes([f.bbox for f in group])
            for i, table_cell in enumerate(table_cells[idx:], idx):
                table_bbox = self.get_bbox_of(table_cell.iter(o=o))
                # Cells that are overlapping in the given Orientation
                #  can not split the Table.
                if table_bbox.is_overlap(normal.name.lower(), group_bbox):
                    idx = i
                    break
                # We can be sure the group splits the Table,
                #  only when encountering a series right/below of the group.
                if getattr(table_bbox, bound) > getattr(group_bbox, bound):
                    splitter.append(group)
                    idx = i
                    break
        return splitter

    def get_splitting_cols(self, contained_cells: Cs) -> list[Cs]:
        """ Return those Cells that split the Table vertically.

        I.e., none of these Cells fit in any column of the Table.

        :param contained_cells: The Cells to check.
            All of these should be contained in the Table.
        :return: The Cells that split the Table vertically.
        """
        cols = cells_to_cols(contained_cells, link_cols=False)
        splitter = self._get_splitting_series(V, cols)
        return splitter

    def get_splitting_rows(self, contained_cells: Cs) -> list[Cs]:
        """ Get the Cells that split the Table horizontally.

        I.e., none of these Cells fit in any row of the Table.

        :param contained_cells: The Cells to check.
            All of these should be contained in the Table.
        :return: The Cells that split the Table horizontally.
        """
        rows = cells_to_rows(contained_cells, link_rows=False)
        splitter = self._get_splitting_series(H, rows)
        return splitter

    def max_split(self, cells: Cs) -> list[Table]:
        """ Split the Table horizontally (if possible) using the given
        Cells and then split each of those vertically (if possible).

        The current Table should not be used after it was split.

        :param cells: The Cells that may split the Table in either Direction.
        :return: The list of Tables.
        """
        contained_cells = self.get_contained_cells(cells)
        if not contained_cells:
            return [self]
        col_splitter = self.get_splitting_cols(contained_cells)
        row_splitter = self.get_splitting_rows(contained_cells)

        col_tables = self.split_at_cells(V, col_splitter)
        tables = []
        for table in col_tables:
            tables += table.split_at_cells(H, row_splitter)

        return list(collapse(tables))

    def _remove_empty_series(self, o: Orientation) -> None:
        n = o.normal
        for cell in list(self.top.iter(o=o)):
            series = list(cell.iter(o=n))
            if any((not isinstance(f, EmptyCell) for f in series)):
                continue
            lower_neighbor = series[0].get_neighbor(o.lower)
            upper_neighbor = series[0].get_neighbor(o.upper)
            unlink_cells(o.lower, series)
            unlink_cells(o.upper, series)
            if lower_neighbor and upper_neighbor:
                neighbors = (list(lower_neighbor.iter(o=n)),
                             list(upper_neighbor.iter(o=n)))
                for (lower_neighbor, upper_neighbor) in zip(*neighbors):
                    lower_neighbor.set_neighbor(o.upper, upper_neighbor)
                continue
            # Need to update the saved end Cells,
            # in case we just removed one of the end Cells.
            if not lower_neighbor:
                self._update_end(N, upper_neighbor)
                self._update_end(W, upper_neighbor)
            if not upper_neighbor:
                self._update_end(S, lower_neighbor)
                self._update_end(E, lower_neighbor)

    def remove_empty_series(self) -> None:
        """ Remove all rows/columns that only contain EmptyCells. """
        self._remove_empty_series(H)
        self._remove_empty_series(V)

    def to_timetable(self) -> TimeTable | None:
        """ Turn this Table into a timetable.

        :return: A valid timetable containing all Cells with a proper type.
        """
        from pdf2gtfs.datastructures.timetable.table import TimeTable
        from pdf2gtfs.datastructures.timetable.stops import Stop
        from pdf2gtfs.datastructures.timetable.entries import (
            TimeTableEntry, TimeTableRepeatEntry, Weekdays,
            )

        def add_cell_to_timetable(e_id: int, cell: C) -> None:
            """ Add the Cell to the timetable.

            How the Cell is added depends on its type.
            """
            match cell.get_type():
                case T.Other | T.Empty | T.Stop:
                    # Only Cells with a proper type are added.
                    # Stops were already added.
                    return
                case T.Time:
                    # Add the Time to the entry
                    #  and ensure the entry will be added to the TimeTable.
                    entries[e_id].set_value(
                        t.stops.get_from_id(stop_id), cell.text)
                    valid_entry_ids.add(e_id)
                case T.EntryAnnotValue:
                    annots = set([a.strip() for a in cell.text.split()])
                    entries[e_id].annotations = annots
                case T.Days:
                    entries[e_id].days = Weekdays(cell.text)
                case T.RouteAnnotValue:
                    entries[e_id].route_name = cell.text
                case T.StopAnnot:
                    t.stops.add_annotation(cell.text, stop_id=stop_id)
                case T.RepeatValue:
                    # Convert the entry to a RepeatEntry
                    #  and ensure the entry will be added to the TimeTable.
                    if not isinstance(entries[e_id], TimeTableRepeatEntry):
                        entries[e_id] = TimeTableRepeatEntry.from_entry(
                            entries[e_id], [cell.text])
                    valid_entry_ids.add(e_id)

        def update_entry_days(days: Weekdays, entry_: TimeTableEntry
                              ) -> Weekdays:
            """ Set the days for the given entry, if it does not have any.

            :param days: The previously encountered days.
            :param entry_: This entry's days are added if it does not have any.
            :return: Either days or the entry's days,
                depending on whether the entry already had days or not.
            """
            if not entry_.days.days:
                entry_.days = days
            return entry_.days

        t = TimeTable()
        o, stops = self.find_stops()
        # Ignore Tables with too few stops. Usually these are false positives.
        if len(stops) < 3:
            return None

        # Add stops to the TimeTable.
        for stop in [Stop(stop.text, i) for i, stop in stops]:
            t.stops.add_stop(stop)

        # Create empty TimeTableEntries for each col/row.
        entries: list[TimeTableEntry]
        entries = [TimeTableEntry("") for _ in self.left.iter(o=o.normal)]
        valid_entry_ids = set()

        # Add each Cell to the TimeTable.
        for stop_id, start in enumerate(self.left.iter(o=o)):
            for entry_id, table_cell in enumerate(start.iter(o=o.normal)):
                add_cell_to_timetable(entry_id, table_cell)

        # Find the first valid days.
        valid_entries = list(entries[idx] for idx in valid_entry_ids)
        # Use all entries, in case the days are not defined within the table.
        previous_days = first_true(entries, lambda e: e.days != []).days

        # Update the days for each entry and add the entries to the TimeTable.
        for entry in valid_entries:
            previous_days = update_entry_days(previous_days, entry)
            t.entries.append(entry)

        return t

    def find_stops(self) -> tuple[Orientation, list[tuple[int, C]]]:
        """ Get the row/column that contains the Stops.

        :return: The Orientation of the Stops, as well as the list of stops,
            with each Stop's row/col index based on Orientation.
        """
        def _find_stops(o: Orientation, start: C | None = None
                        ) -> list[tuple[int, C]]:
            if start is None:
                start = self.left
            for cell in start.iter(o=o.normal):
                series = [(i, f) for i, f in enumerate(cell.iter(o=o))
                          if f.has_type(T.Stop, strict=True)]
                if not series:
                    continue
                return series
            return []

        v_stops = _find_stops(V)
        h_stops = _find_stops(H)
        return (V, v_stops) if len(v_stops) > len(h_stops) else (H, h_stops)

    def cleanup(self, first_table: Table | None) -> None:
        """ Infer the CellTypes of all Cells.

        This will infer the Type multiple times,
        to accomodate for changes in the type based on a previous inference.

        :param first_table: If None, the current Table is the first Table.
            Otherwise, the first Table will be used to determine
            whether the Days, etc. are in the header or in the footer.
        """

        def infer_cell_types() -> None:
            """ Infer the CellTypes of each Cell.

            This will infer the type multiple times, to accomodate
            for changes in the type based on a previous inference.
            """
            # TODO: Test if it makes a difference, running this twice.
            # TODO: Instead, we could try to store the Type of each Cell and
            #  only stop inference, when they no longer change.
            #  Should watch for loops then, though.
            for starter in self.left.row:
                for cell in starter.col:
                    cell.type.infer_type_from_neighbors()
            for starter in self.left.row:
                for cell in starter.col:
                    cell.type.infer_type_from_neighbors()

        def merge_stops(o: Orientation, stops: list[tuple[int, C]]) -> None:
            """ Merge consecutive Cells of Type Stop. """
            allow_merge = True
            allowed_types = [T.Stop, T.Empty]
            while True:
                stop: C | None = None
                for _, stop in stops:
                    neighbor: C = stop.get_neighbor(o.normal.upper)
                    if neighbor and neighbor.get_type() in allowed_types:
                        continue
                    allow_merge = False
                    break
                if not stop or not allow_merge:
                    break
                series = "cols" if o == V else "rows"
                logger.info(
                    f"Found two consecutive stop {series}. Merging...")
                merge_series(stop, o.normal.upper)

        def merge_consecutive_days() -> None:
            """ Merge multi-word DaysCells that were split. """
            first_col = self.left.col
            for row_starter in first_col:
                for cell in row_starter.row:
                    if not cell.has_type(T.Days, strict=True):
                        continue
                    neighbors = cell.get_neighbors(directions=[E],
                                                   allow_empty=False)
                    while (neighbors
                           and neighbors[0].has_type(T.Days, strict=True)
                           and cell.text.lower() not in Config.header_values):
                        cell.text += " " + neighbors[0].text
                        self.replace_cell(neighbors[0], EmptyCell())
                        neighbors = cell.get_neighbors(directions=[E],
                                                       allow_empty=False)

        infer_cell_types()
        merge_stops(*self.find_stops())
        merge_consecutive_days()
        self.remove_duplicate_days(H, first_table)

    def remove_duplicate_days(self, o: Orientation, ref_table: Table) -> None:
        """ When a Table contains more than one row/col of Days,
        only keep the first/last,
        based on what the first Table of the page looks like.

        :param o: The Orientation the days are in.
            Currently only H is supported.
        :param ref_table: The Table used as reference.
            This should be the first table on the page.
        """
        # TODO: Theoretically, this could handle o = V as well.
        #  However, because we currently allow Days to be only inside rows,
        #  logically it does not make sense to run it like that.
        # TODO: There is also the issue on how to detect whether the tables
        #  use rows or cols for the Days.
        if ref_table is None:
            return
        # Use the first Table on the page to determine, which days row/col
        # is the correct one, in case multiple days rows or cols exist.
        days = self.of_type(T.Days, o)
        # This Table only has one row containing Days.
        if len(days) == 1:
            return
        # Get the first row of the reference Table.
        ref_days_list = ref_table.of_type(T.Days, o, single=True)
        ref_days = [] if not ref_days_list else ref_days_list[0]
        if not days:
            # Duplicate the first Tables days and add to self.
            self.potential_cells += [day.duplicate() for day in ref_days]
            self.expand_all()
            return
        # Use the first days row/col if its col/row index in the
        #  first half of the col/row. Otherwise, use the last days row/col.
        ref_normal = list(ref_days[0].iter(o.normal))
        ref_normal_days_index = ref_normal.index(ref_days[0])
        first = ref_normal_days_index < len(ref_normal) / 2
        first_or_last = "first" if first else "last"
        logger.info("Found multiple rows containing Cells of type Days for "
                    f"Table {self}. Selecting the {first_or_last} row, "
                    f"because the first Table of the current page uses the "
                    f"{first_or_last} row as well.")
        # Remove Days as a possible type of all other days
        invalid_days = days[1:] if first else days[:-1]
        for days in invalid_days:
            for day in days:
                del day.type.possible_types[T.Days]
                day.type.infer_type_from_neighbors()

    def of_type(self, typ: T, o: Orientation = V, single: bool = False,
                strict: bool = True) -> list[list[C]]:
        """ Return one or all series' of the given Type.

        Each series will be partial, in the sense that
        each Cell will be of the given type.

        Thus, in general,
        the series is different from the row/col of the series' Cells.

        :param typ: The Type each Cell in the returned row will have.
        :param o: The Orientation the Cells in the returned lists will have.
        :param single: Whether to only return the first series encountered.
        :param strict: If type checking should be strict or not.
        :return: A list of lists,
            where each sublist contains Cells of the given Type.
        """
        cells_of_type: list[list[C]] = []
        for starter in self.left.iter(o=o.normal):
            cells_of_type.append([])
            for cell in starter.iter(o=o):
                if cell.has_type(typ, strict=strict):
                    cells_of_type[-1].append(cell)
            if not cells_of_type[-1]:
                cells_of_type.pop()
            # Only return Cells of the first row/col
            # that contains Cells of the given type.
            if single and cells_of_type:
                return cells_of_type
        return cells_of_type

    def replace_cell(self, cell: Cell, new_cell: Cell) -> None:
        if cell.prev:
            cell.prev.next = new_cell
        if cell.next:
            cell.next.prev = new_cell
        if cell.above:
            cell.above.below = new_cell
        if cell.below:
            cell.below.above = new_cell


def group_cells_by(cells: Iterable[C],
                   same_group_func: Callable[[C, C], bool],
                   pre_sort_keys: str | Iterable[str] | None,
                   group_sort_keys: str | Iterable[str] | None) -> list[Cs]:
    """ Group the given Cells using the given function.

    :param cells: The Cells that should be grouped.
    :param same_group_func: A function that takes two Cells and
        returns whether they are in the same group. False, otherwise.
    :param pre_sort_keys: Sort the Cells before grouping using this as key.
    :param group_sort_keys: Each group will be sorted using this as key.
    :return: A list of groups of Cells.
    """
    groups: list[Cs] = []
    if pre_sort_keys:
        pre_sorter = attrgetter(*always_iterable(pre_sort_keys))
        cells = sorted(cells, key=pre_sorter)

    group_sorter = None
    if group_sort_keys:
        group_sorter = attrgetter(*always_iterable(group_sort_keys))
    for group in split_when(cells, same_group_func):
        if group_sorter:
            group.sort(key=group_sorter)
        groups.append(group)

    return groups


def cells_to_cols(cells: Cs, *, link_cols: bool = True) -> list[Cs]:
    """ Groups the Cells into a collection of cols.

    :param cells: The Cells that are grouped into cols.
    :param link_cols: Whether to link the Cells of a col.
    :return: A list of all cols.
    """
    def _same_col(c1: C, c2: C) -> bool:
        """ Two Cells are in the same col if they overlap horizontally. """
        return not c1.bbox.is_h_overlap(c2.bbox)

    cols = group_cells_by(cells, _same_col, "bbox.x0", "bbox.y0")
    if not link_cols:
        return cols

    for col in cols:
        link_cells(S, col)
    return cols


def cells_to_rows(cells: Cs, *, link_rows: bool = True) -> list[Cs]:
    """ Group the Cells into a collection of rows.

    :param cells: The Cells that will be part of the row.
    :param link_rows: Whether to link the Cells in a row.
    :return: A list of all rows.
    """
    def _same_row(c1: C, c2: C) -> bool:
        """ Two Cells are in the same row if they overlap vertically. """
        return not c1.bbox.is_v_overlap(c2.bbox)

    rows: list[Cs] = group_cells_by(cells, _same_row, "bbox.y0", "bbox.x0")
    if not link_rows:
        return rows

    for row in rows:
        link_cells(E, row)
    return rows


def link_cells(d: Direction, cells: Cs) -> None:
    """ Link the fields in the given Direction.

    The Cells will be linked in the opposite Direction, implicitely.

    :param d: The Direction to link in.
    :param cells: The Cells that should be linked.
    """
    p = peekable(cells)
    for cell in p:
        cell.update_neighbor(d, p.peek(None))


def unlink_cells(d: Direction, cells: Cs) -> None:
    """ Remove the links to any other Cells in the given Direction.

    The links that are removed can be linked to arbitrary Cells.

    :param d: The Direction each Cell's neighbors will be removed from.
    :param cells: The Cells to remove the links from.
    """
    for cell in cells:
        cell.del_neighbor(d)


def link_rows_and_cols(partial_rows: list[Cs], partial_cols: list[Cs]
                       ) -> tuple[list[Cs], list[Cs]]:
    """ Link the rows and columns, such that each Cell can be reached using
    any other Cell and the Cell's get_neighbor method.

    :param partial_rows: The list of Cells representing the rows.
    :param partial_cols: The list of Cells representing the cols.
    """
    def _fill_gaps_in_column(relative_to: Cs, partial_col: Cs) -> Cs:
        """ Add EmptyCells in place of missing Cells.

        :param relative_to: A complete col. This is used to determine,
            which of the Cells are missing in the partial col.
        :param partial_col: A col that may have missing Cells.
        :return: The complete col.
        """
        head = insert_empty_cells_from_map(V, relative_to, partial_col)
        return list(head.iter(S))

    # No complete relative column exists for the first column,
    #  so we use the first Cell of each row.
    left_most_cell_of_each_row = [row[0] for row in partial_rows]
    cols = [_fill_gaps_in_column(left_most_cell_of_each_row, partial_cols[0])]

    for col in partial_cols[1:]:
        cols.append(_fill_gaps_in_column(cols[-1], col))

    # Link the columns with each other.
    for col1, col2 in pairwise(cols):
        for f1, f2 in zip(col1, col2, strict=True):
            # The neighbor of f2 in Direction W is deleted implicitly.
            f1.del_neighbor(E)
            f1.set_neighbor(E, f2)

    # Get the (now) complete rows.
    rows: list[Cs] = [list(cell.iter(E)) for cell in cols[0]]
    return cols, rows


def merge_small_cells(o: Orientation, ref_cells: Cs, cells: Cs) -> None:
    """ Merge Cells that are overlapping with the same ref_cell.

    If two or more Cells are overlapping with the same ref_cell,
    the former are all merged into a single Cell.

    :param o: The Orientation used check for overlap.
    :param ref_cells: The Cells used as reference.
    :param cells: The Cells that might be merged.
    """
    def get_cell_overlaps(start_: int, cell_: C) -> tuple[int, Cs]:
        """ Find those ref_cells the given Cell overlaps with.

        :param start_: The index of the ref_cell to start at. Used to skip
            ref_cells that did not overlap with the previous col's Cell.
        :param cell_: The Cell we want to find the overlapping ref_cells for.
        :return: The index of the first overlapping ref_cell,
            and the ref_cells that overlap with the given Cell.
        """
        cell_overlaps = []
        overlap_func: Callable[[BBox], Callable[[BBox, float], bool]]
        overlap_func = methodcaller(o.normal.overlap_func, cell_.bbox, 0.8)
        # Start looking for overlapping ref_cells only from the previous
        #  ref_cell. That way we skip those ref_cells, we know can not overlap.
        # This works because both the cells and the ref_cells are sorted.
        for i, ref_cell in enumerate(ref_cells[start_:], start_):
            # Use the BBox of the ref_cells col/row, in case the ref_cell
            #  itself is smaller.
            bbox = ref_cell.table.get_bbox_of(ref_cell.iter(o=o))
            if overlap_func(bbox):
                if not cell_overlaps:
                    start_ = i
                cell_overlaps.append(ref_cell)
                continue
            # No need to look for further overlaps
            #  if a previous ref_cell overlapped and the current one doesn't.
            if cell_overlaps:
                break
        return start_, cell_overlaps

    # TODO: Try to have ref_cells contain the maximum number of TimeCells.
    #  That way, Days columns, for example,  won't fuck up anything above them.
    if len(cells) < 2:
        return
    overlaps = {}
    start = 0
    # For each Cell find those ref_cells the Cell overlaps with.
    for cell in cells:
        start, overlaps[cell] = get_cell_overlaps(start, cell)

    # Merge consecutive Cells, iff they are overlapping with the same ref_cell.
    c1 = cells[0]
    c2 = cells[1]
    while c2:
        has_same_overlap = any([overlap in overlaps[c1]
                                for overlap in overlaps[c2]])
        if not has_same_overlap:
            c1, c2 = c2, c2.get_neighbor(o.normal.upper)
            continue
        c1.merge(c2)
        cells.remove(c2)
        # c1 has all neighbors of c2 after merge.
        c2 = c1.get_neighbor(o.normal.upper)


def insert_empty_cells_from_map(o: Orientation, ref_cells: Cs, cells: Cs) -> C:
    """ Insert EmptyCells as neighbors of the Cells, until Cells and
    ref_cells can be mapped (i.e., can be neighbors).

    :param o: V or H.
        If V, ref_cells should be a column of a Table; if H, a row instead.
    :param ref_cells: The Cells used as reference.
    :param cells: The Cells that are used as starting point.
        All of these will be part of the linked Cell list.
    :return: The (possibly new, empty) first Cell.
    """
    def add_empty_cell(d: Direction, cell_: C, ref_cell_: C) -> EmptyCell:
        """ Create a new EmptyCell and add it as the neighbor of Cell.

        :param d: The EmptyCell will be the Cell's neighbor in this Direction.
        :param cell_: The Cell the EmptyCell is inserted next to.
            It is also used to set the EmptyCell's BBox.
        :param ref_cell_: This is used to set the EmptyCell's BBox.
        """
        empty_cell = EmptyCell()
        if o == H:
            empty_cell.set_bbox_from_reference_cells(ref_cell_, cell_)
        else:
            empty_cell.set_bbox_from_reference_cells(cell_, ref_cell_)
        cell_.set_neighbor(d, empty_cell)
        return empty_cell

    # Add EmptyCells at the start and between other Cells.
    idx = 0
    cell_count = 0
    for ref_cell in ref_cells:
        if idx >= len(cells):
            break
        cell_count += 1
        cell = cells[idx]
        if ref_cell.table:
            bbox = ref_cell.table.get_bbox_of(ref_cell.iter(o=o.normal))
        else:
            bbox = ref_cell.bbox
        if bbox.is_overlap(o.name.lower(), cell.bbox, 0.8):
            idx += 1
            continue
        add_empty_cell(o.lower, cell, ref_cell)

    # Add empty EmptyCells at the end.
    cell = cells[-1]
    while cell_count < len(ref_cells):
        cell = add_empty_cell(o.upper, cell, ref_cells[cell_count])
        cell_count += 1

    # Return th lower end (i.e., first) Cell.
    return cells[0].get_last(o.lower)


def insert_cells_in_col(col: Cs, cells: Cs) -> None:
    """ Insert the Cells into the given col, replacing existing Cells.

    :param col: The column the Cells are inserted into.
    :param cells: The Cells that will be inserted into the column.
    """

    def replace_cell(to_replace: C, replace_with: C) -> None:
        """ Replace one Cell with another Cell.

        :param to_replace: The Cell that will be replaced.
        :param replace_with: The Cell that will be inserted instead.
        """
        # The new Cell should not have any neighbors.
        assert not replace_with.has_neighbors(o=V)
        assert not replace_with.has_neighbors(o=H)
        for d in D:
            neighbor = to_replace.get_neighbor(d)
            if not neighbor:
                continue
            to_replace.del_neighbor(d)
            neighbor.set_neighbor(d.opposite, replace_with)
        to_replace.table = None

    last_id = 0
    for cell in cells:
        for i, col_cell in enumerate(col[last_id:], last_id):
            if not col_cell.is_overlap(V, cell, 0.8):
                continue
            assert col_cell.is_overlap(H, cell, 0.8)
            replace_cell(col_cell, cell)
            last_id = i + 1
            break
