""" The new table, that is able to detect tables regardless of orientation. """

from __future__ import annotations

import logging
from itertools import pairwise
from operator import attrgetter
from typing import Callable, Generator, Iterable, Iterator, TYPE_CHECKING

from more_itertools import (
    always_iterable, collapse, first_true, peekable, split_when,
    )

from pdf2gtfs.datastructures.pdftable.bbox import BBox
from pdf2gtfs.datastructures.table.bounds import select_adjacent_cells
from pdf2gtfs.datastructures.table.cell import (
    EmptyCell, C, Cs, OC,
    )
from pdf2gtfs.datastructures.table.celltype import T
from pdf2gtfs.datastructures.table.direction import (
    D, Direction, E, H, N, Orientation, S, V, W,
    )


if TYPE_CHECKING:
    from pdf2gtfs.datastructures.timetable.table import TimeTable


logger = logging.getLogger(__name__)


class Table:
    """ Table representation using Fields mapped in all four directions
        (= QuadLinkedList). Able to expand in all directions.
    """
    def __init__(self, first_node: C, last_node: C):
        self.bboxes: dict[int: int] = {}
        self._left = None
        self._right = None
        self._top = None
        self._bot = None
        self._update_end_node(W, first_node)
        self._update_end_node(E, last_node)
        self._update_end_node(N, first_node)
        self._update_end_node(S, last_node)
        # Update table on all nodes.
        for row_cell in self.top.row:
            for col_cell in row_cell.col:
                col_cell.table = self
        self.other_cells = None

    @property
    def top(self) -> OC:
        """ One of the nodes in the top row. """
        return self.get_end_node(d=N)

    @property
    def left(self) -> OC:
        """ One of the nodes in the left-most column. """
        return self.get_end_node(d=W)

    @property
    def bot(self) -> OC:
        """ One of the nodes in the bottom column. """
        return self.get_end_node(d=S)

    @property
    def right(self) -> OC:
        """ One of the nodes in the right-most column. """
        return self.get_end_node(d=E)

    @property
    def bbox(self) -> BBox:
        """ The bbox, that contains every cell of the table. """
        return self.get_bbox_of(collapse((self.left.col, self.top.row,
                                          self.right.col, self.bot.row)))

    @staticmethod
    def from_cells(cells: Cs) -> Table:
        """ Create a new table from the given cells.

        :param cells:
        :return:
        """
        cols = cells_to_cols(cells)
        rows = cells_to_rows(cells)
        link_rows_and_cols(rows, cols)
        t = Table(cols[0][0], rows[-1][-1])
        return t

    def get_end_node(self, d: Direction) -> OC:
        """ Return one of the end nodes in the given direction.

        :param d: The direction to look for the end node in.
        """
        # Get the current end node.
        node: OC = getattr(self, d.p_end)
        o = d.default_orientation
        d2 = o.normal.lower if d == o.lower else o.normal.upper
        if not node.has_neighbors(d=d) and not node.has_neighbors(d=d2):
            return node

        self._update_end_node(d, node)
        return self.get_end_node(d)

    def _set_end_node(self, d: Direction, node: OC) -> None:
        """ Store the last node in the given direction to node.

        This will fail if node has a neighbor in the given direction.

        :param d: The direction, which specifies, where to store the node.
        :param node: The node to be stored.
        """
        assert node.get_neighbor(d) is None
        setattr(self, d.p_end, node)

    def _update_end_node(self, d: Direction, start: C) -> None:
        """ Update the end node in the given direction to the farthest/last
        node in that direction.

        Always ensures that the end node in the lower direction of an
        orientation is also the end node in the lower direction of the
        orientation's normal orientation. That is, if d is N (i.e. V.lower)
        the end node the same as when d is W (i.e. H.lower). Analogous for S/E.

        :param d: The direction to look for the last node.
        :param start: The node to use to look for the end node in d.
        """
        o = d.default_orientation
        d2 = o.normal.lower if d == o.lower else o.normal.upper
        self._set_end_node(d, start.get_last(d).get_last(d2))

    def get_list(self, o: Orientation, node: OC = None) -> list[C]:
        """ Return the full list of nodes in the given orientation.

        :param o: The orientation the nodes will be in.
        :param node: The node used to get a specific row/column. If set to
         None, the first/top node will be used instead.
        """
        if not node:
            node = self.get_end_node(o.lower)
        return list(node.iter(o.upper, True))

    def insert(self, d: Direction, rel_node: OC, new_node: C) -> None:
        """ Inserts the node relative to the rel_node in the given direction.

        :param d: The relative direction of node to rel_node, after insertion.
        :param rel_node: Either a node or None. If node, insertion happens
         adjacent to it. If None, insert as the last node in d.
        :param new_node: The node that will be inserted.
        """
        o = d.default_orientation
        normal = o.normal

        # TODO NOW: Check that each new_node only has neighbors,
        #  that are in new_nodes
        new_nodes = list(new_node.iter(normal.upper))
        # If we want to insert a column (i.e. vertical) at the beginning/end,
        # we need a row (i.e. horizontal) to get the first/last column.
        if rel_node is None:
            rel_node = self.get_end_node(normal.lower)
        rel_nodes = self.get_list(normal, rel_node)

        # Strict, to ensure the same number of nodes.
        for rel_node, new_node in zip(rel_nodes, new_nodes, strict=True):
            rel_node.set_neighbor(d, new_node)
            new_node.table = self

    def get_series(self, o: Orientation, node: C) -> Generator[C]:
        """ The row or column the node resides in.

        :param o: The orientation of the series, i.e. whether to return
            row (H) or column (V).
        :param node: The node in question.
        :return: A generator that yields all objects in the series.
        """
        return node.iter(o.upper, True)

    def get_bbox_of(self, cells: Iterator[C]) -> BBox:
        """ Return the combined bbox of cells.

        Also caches the results in case the same bbox is requested again,
        using the hash of the cells bboxes.

        :param cells: The cells to get the bbox from.
        :return: A bbox, that contains all the cells' bboxes.
        """
        bboxes = [c.bbox for c in cells if not isinstance(c, EmptyCell)]
        # Actual bbox calculation and caching.
        # No need to cache a single bbox.
        if len(bboxes) == 1:
            return bboxes[0]
        # If a bboxes' coordinates change, its hash changes as well.
        nodes_hashes = sorted(map(hash, bboxes))
        nodes_hash = hash("".join(map(str, nodes_hashes)))
        if nodes_hash not in self.bboxes:
            self.bboxes[nodes_hash] = BBox.from_bboxes(bboxes)
        return self.bboxes[nodes_hash]

    def get_empty_cell_bbox(self, cell: EmptyCell) -> BBox:
        """ The bbox of an empty cell is defined as its row's x-coordinates
        and its col's y-coordinates.

        :param cell: The EmptyField the bbox was requested for.
        :return: A bbox, that is contained by both the row/col, while having
            the row's height and the col's width.
        """
        row_bbox = self.get_bbox_of(cell.row)
        col_bbox = self.get_bbox_of(cell.col)
        return BBox(col_bbox.x0, row_bbox.y0, col_bbox.x1, row_bbox.y1)

    def expand(self, d: Direction) -> bool:
        """ Expand the table in the given direction using the given cells.

        :param d: The direction the expansion is done towards.
        :return: Whether any cells were added.
        """
        if self.other_cells is None:
            raise Exception("Other cells need to be added to this table, "
                            "before trying to expand.")
        normal = d.default_orientation.normal
        ref_cells = list(self.get_series(normal, self.get_end_node(d)))

        bboxes = [self.get_bbox_of(self.get_series(d.default_orientation, f))
                  for f in ref_cells]
        adjacent_cells = select_adjacent_cells(d, bboxes, self.other_cells)
        if not adjacent_cells:
            return False

        link_cells(normal.upper, adjacent_cells)
        merge_small_cells(d.default_orientation, ref_cells, adjacent_cells)

        head = insert_empty_cells_from_map(
            normal, ref_cells, adjacent_cells)
        try:
            self.insert(d, ref_cells[0], head)
        except ValueError:
            # Insertion has failed. This usually (hopefully) means that the
            # adjacent cells are not part of the table.
            unlink_cells(d, ref_cells)
            return False
        # Only remove cells that were added.
        for cell in adjacent_cells:
            self.other_cells.remove(cell)
        return True

    def get_contained_cells(self, cells: Cs) -> Cs:
        """ Get all cells, that are within the tables' cells' combined bbox.

        :param cells: The cells that might be contained by the table.
        :return: A list of all cells of the given cells, that have a bbox
            that is contained in the tables bbox.
        """
        def _both_overlap(cell: C) -> bool:
            return (bbox.is_v_overlap(cell.bbox, 0.8) and
                    bbox.is_h_overlap(cell.bbox, 0.8))

        bbox = BBox.from_bboxes(
            [self.get_bbox_of(self.left.col),
             self.get_bbox_of(self.right.col),
             self.get_bbox_of(self.top.row),
             self.get_bbox_of(self.bot.row)])

        cells = list(filter(_both_overlap, cells))
        return cells

    def get_containing_col(self, cell: C) -> Cs | None:
        """ Find the column that contains (via bbox-overlap) the cell.

        :param cell: The cell, we want to know the column of.
        :return: The column, that contains the cell or None if no
            such column exists.
        """
        for col_cell in self.left.iter(E):
            if col_cell.is_overlap(H, cell, 0.8):
                return list(col_cell.col)
        return None

    def get_col_left_of(self, cell: C) -> Cs:
        """ Get the last column left of the cell.

        That is, the column right of whichever column this function returns
        (if any) either contains the cell or is located right of the cell.

        :param cell: The cell we are using as reference.
        :return: The last column left of the cell or None, if no such
         column exists.
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
            self.left.row, default=self.left, pred=_is_right_of_cell)
        # TODO NOW: Will fail if default.
        return col_right_of_cell.prev.col

    def insert_repeat_cells(self, cells: Cs) -> None:
        """ Find the cells that are part of a repeat interval and add
            them to the table.

        :param cells: The cells that are checked for repeat intervals.
        """
        identifiers = self.get_repeat_identifiers(cells)
        if not identifiers:
            return
        values = self.get_repeat_values(identifiers, cells)
        for cell in identifiers + values:
            cells.remove(cell)
        # Add identifiers and their values to table.
        # Group repeat cells by col and link them.
        repeat_groups = cells_to_cols(identifiers + values)
        # Insert the repeat_groups each into a new or existing column.
        for group in repeat_groups:
            col = self.get_containing_col(group[0])
            if col:
                unlink_cells(S, group)
                insert_cells_in_col(col, group)
                continue
            col = list(self.get_col_left_of(group[0]))
            head = insert_empty_cells_from_map(V, col, group)
            self.insert(E, col[0], head)

    def get_repeat_identifiers(self, cells: Cs) -> Cs:
        """ Return those cells, that are repeat identifiers.

        :param cells: The cells that may be identifiers.
        :return: Those cells that are repeat identifiers.
        """
        contained_cells = self.get_contained_cells(cells)
        repeat_identifiers = [f for f in contained_cells
                              if f.has_type(T.RepeatIdent)]
        if repeat_identifiers:
            cells_to_cols(repeat_identifiers)
        return repeat_identifiers

    def get_repeat_values(self, identifiers: Cs, cells: Cs) -> Cs:
        """ Given the identifiers, find those cells that are repeat values.

        :param identifiers: The repeat identifiers.
        :param cells: The cells that are evaluated.
        :return: Those cells that are repeat values.
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
        rows = [cell.row for cell in self.left.col]
        cols = [cell.col for cell in self.top.row]
        # The maximum length of a cells text in each column.
        col_len = [max(map(len, map(getter_func, col))) for col in cols]

        delim = " | "
        lines = []
        for row in rows:
            values = [f"{getter_func(f): {align_func(f)}{col_len[i]}}"
                      for i, f in enumerate(row)][:col_count]
            lines += [delim.lstrip() + delim.join(values) + delim.rstrip()]

        print("\n".join(lines) + "\n")

    def print(self, col_count: int | None = 8) -> None:
        """ Print the table to stdout.

        :param col_count: The number of characters each line can have.
        """
        def get_text_align(f) -> str:
            """ Right align all data cells; left align everything else.
            :param f: This cells text is checked.
            :return: The format char used for alignment.
            """
            return ">" if f.get_type() == T.Data else "<"

        self._print(attrgetter("text"), get_text_align, col_count)

    def print_types(self, col_count: int = None) -> None:
        """ Print the inferred type of each cell, instead of its text. """
        def _get_type_name(f: C) -> str:
            if isinstance(f, EmptyCell):
                return ""
            return f.get_type().name

        self._print(_get_type_name, col_count=col_count)

    def split_at_cells(self, o: Orientation, splitter: list[Cs]
                       ) -> list[Table]:
        """ Split the table at the given cells.

        :param o: The orientation to split in.
        :param splitter: The cells used to split the table.
        :return: A list of tables, where each table contains only cells,
            that are between the given splitter.
        """
        if not splitter:
            return [self]
        table_cells = self._split_at_splitter(o, splitter)

        tables = []
        for table_cell in table_cells:
            head = table_cell[0]
            # The splitter should not implicitly be part of the table.
            if head.table != self:
                continue
            cell = None
            # Unlink last row/col of each table, based on o.
            for cell in self.get_series(o, table_cell[-1]):
                cell.del_neighbor(o.normal.upper)
            table = Table(head, cell)
            table.remove_empty_series()
            tables.append(table)

        return tables

    def _get_splitting_series(self, o: Orientation, grouped_cells: list[Cs]
                              ) -> list[Cs]:
        splitter = []
        idx = 0
        n = o.normal
        table_cells = list(self.get_series(n, self.get_end_node(n.upper)))
        bound = "y0" if o == H else "x0"
        for group in grouped_cells:
            group_bbox = BBox.from_bboxes([f.bbox for f in group])
            for i, table_cell in enumerate(table_cells[idx:], idx):
                table_bbox = self.get_bbox_of(self.get_series(o, table_cell))
                # Fields that are overlapping in the given orientation
                #  can' split the table.
                if table_bbox.is_overlap(o.normal.name.lower(), group_bbox):
                    idx = i
                    break
                # We can be sure the group splits the table, only when
                #  encountering a series right/below of group.
                if getattr(table_bbox, bound) > getattr(group_bbox, bound):
                    splitter.append(group)
                    idx = i
                    break
        return splitter

    def get_splitting_cols(self, contained_cells: Cs) -> list[Cs]:
        """ Return those cells, that split the table vertically,
            i.e. none of these cells fit in any column of the table.

        :param contained_cells: The cells to check. All of these should be
            contained in the table.
        :return: The cells that split the table vertically.
        """
        cols = cells_to_cols(contained_cells, link_cols=False)
        splitter = self._get_splitting_series(V, cols)
        return splitter

    def get_splitting_rows(self, contained_cells: Cs) -> list[Cs]:
        """ Get the cells that split the table horizontally,
            i.e. none of these cells fit in any row of the table.

        :param contained_cells: The cells to check. All of these should
            be contained in the table.
        :return: The cells that split the table horizontally.
        """
        rows = cells_to_rows(contained_cells, link_rows=False)
        splitter = self._get_splitting_series(H, rows)
        return splitter

    def max_split(self, cells: Cs) -> list[Table]:
        """ Split the table horizontally (if appliccable) using the given
            cells and then split each of those vertically (if appliccable).

        The current table should not be used after it was split.

        :param cells: The cells that may split the table in either direction.
        :return: The list of tables.
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

    def _split_at_splitter(self, o: Orientation, splitter: list[Cs]
                           ) -> list[Cs]:
        def _same_table(cell1: C, cell2: C) -> bool:
            return cell1.table != cell2.table

        cells = list(self.get_series(o.normal, self.get_end_node(o.lower)))
        cells += list(collapse(splitter))
        pre_sorter = "bbox.y0" if o == H else "bbox.x0"
        return group_cells_by(cells, _same_table, pre_sorter, None)

    def _remove_empty_series(self, o: Orientation) -> None:
        n = o.normal
        for cell in list(self.get_series(o, self.top)):
            series = list(self.get_series(n, cell))
            if any((not isinstance(f, EmptyCell) for f in series)):
                continue
            lower_neighbor = series[0].get_neighbor(o.lower)
            upper_neighbor = series[0].get_neighbor(o.upper)
            unlink_cells(o.lower, series)
            unlink_cells(o.upper, series)
            if lower_neighbor and upper_neighbor:
                neighbors = (list(self.get_series(n, lower_neighbor)),
                             list(self.get_series(n, upper_neighbor)))
                for (lower_neighbor, upper_neighbor) in zip(*neighbors):
                    lower_neighbor.set_neighbor(o.upper, upper_neighbor)
                continue
            # Need to update saved nodes, in case we just removed one
            # of the end nodes.
            if not lower_neighbor:
                self._update_end_node(N, upper_neighbor)
                self._update_end_node(W, upper_neighbor)
            if not upper_neighbor:
                self._update_end_node(S, lower_neighbor)
                self._update_end_node(E, lower_neighbor)

    def remove_empty_series(self) -> None:
        """ Remove all rows/columns that only contain EmptyFields. """
        self._remove_empty_series(H)
        self._remove_empty_series(V)

    def to_timetable(self) -> TimeTable | None:
        """ Turn this table into a timetable.

        :return: A valid timetable containing all cells
            that have a proper type.
        """
        from pdf2gtfs.datastructures.timetable.table import TimeTable
        from pdf2gtfs.datastructures.timetable.stops import Stop
        from pdf2gtfs.datastructures.timetable.entries import (
            TimeTableEntry, TimeTableRepeatEntry, Weekdays,
            )

        def add_cell_to_timetable() -> None:
            """ Add the cell to the timetable.

            How the cell is added depends on its type.
            """
            match cell.get_type():
                case T.Other | T.Empty | T.Stop:
                    return
                case T.Data:
                    stop = t.stops.get_from_id(stop_id)
                    entries[e_id].set_value(stop, cell.text)
                    non_empty_entries.add(e_id)
                case T.EntryAnnotValue:
                    annots = set([a.strip() for a in cell.text.split()])
                    entries[e_id].annotations = annots
                case T.Days:
                    entries[e_id].days = Weekdays(cell.text)
                case T.RouteAnnotValue:
                    entries[e_id].route_name = cell.text
                case T.StopAnnot:
                    stop = t.stops.get_from_id(stop_id)
                    t.stops.add_annotation(cell.text, stop=stop)
                case T.RepeatValue:
                    e = entries[e_id]
                    if not isinstance(entries[e_id], TimeTableRepeatEntry):
                        entries[e_id] = TimeTableRepeatEntry(
                            "", [cell.text])
                        entries[e_id].days = e.days
                        entries[e_id].route_name = e.route_name
                        entries[e_id].annotations = e.annotations
                    non_empty_entries.add(e_id)

        t = TimeTable()
        o, stops = self.find_stops()
        # TODO NOW: Add to config min_stops
        # Ignore tables with too few stops. Usually these are false positives.
        if len(stops) < 3:
            return None
        n = o.normal
        tt_stops = [Stop(stop.text, i) for i, stop in stops]
        for stop in tt_stops:
            t.stops.add_stop(stop)

        entries: list[TimeTableEntry] = [
            TimeTableEntry("") for _ in self.get_series(n, self.left)]
        non_empty_entries = set()

        for stop_id, start in enumerate(self.get_series(o, self.left)):
            for e_id, cell in enumerate(self.get_series(n, start)):
                add_cell_to_timetable()

        first_days = first_true((entries[e_id].days
                                 for e_id in non_empty_entries),
                                lambda d: d.days != [])
        for e_id in non_empty_entries:
            entry = entries[e_id]
            if not entry.days.days:
                entry.days = first_days
            first_days = entry.days
            t.entries.append(entry)
        return t

    def find_stops(self) -> tuple[Orientation, list[tuple[int, C]]]:
        """ Get the row/column, that contains the stops.

        :return: The orientation of the stops, as well as the list of
            stops, with each stop's row/col index based on orientation.
        """
        def _find_stops(o: Orientation, start: C | None = None
                        ) -> list[tuple[int, C]]:
            for cell in self.get_series(o.normal, start or self.left):
                series = [(i, f)
                          for i, f in enumerate(self.get_series(o, cell))
                          if f.get_type() == T.Stop]
                if not series:
                    continue
                return series
            return []

        v_stops = _find_stops(V)
        h_stops = _find_stops(H)
        return (V, v_stops) if len(v_stops) > len(h_stops) else (H, h_stops)

    def expand_all(self) -> None:
        """ Exhaustively expand the table in the lower directions (N, W). """
        expanded = True
        while expanded:
            expanded = False
            for d in D:
                if d in [S, E]:
                    continue
                expanded |= self.expand(d)

    def infer_cell_types(self, first_table: Table | None) -> None:
        """ Infer the cell types of all cells.

        This will infer the type multiple times,
        to accomodate changes in the type based on the earlier inference.

        :param first_table: If None, the current table is the first table.
            Otherwise, the first table will be used to determine if the
            Days, etc. are in the header or in the footer.
        """
        # TODO: Test if it makes a difference, running this twice.
        for starter in self.left.row:
            for cell in starter.col:
                cell.type.infer_type_from_neighbors()
        for starter in self.left.row:
            for cell in starter.col:
                cell.type.infer_type_from_neighbors()
        self.merge_stops()

        if first_table is None:
            return
        # Use the first table on the page to determine, which days row/col
        # is the correct one, in case multiple days rows or cols exist.
        days_rows = self.of_type(T.Days, H)
        first_table_days_rows = first_table.of_type(T.Days, H, single=True)
        if not first_table_days_rows:
            first_days_row = []
        else:
            first_days_row = first_table_days_rows[0]
        if not days_rows:
            # Duplicate -> add to self.
            for day in first_days_row:
                self.other_cells.append(day.duplicate())
            self.expand_all()
            return
        if len(days_rows) == 1:
            return
        first_table_col = list(first_days_row[0].col)
        first_days_row_idx = first_table_col.index(first_days_row[0])
        first = first_days_row_idx < len(first_table_col) / 2
        first_or_last = "first" if first else "last"
        logger.info("Found multiple rows containing cells of type Days for "
                    f"table {self}. Selecting the {first_or_last}, because "
                    f"the first table of the current page does so as well.")
        # TODO: Do this for other types as well?
        # Remove Days as possible type of all other days_rows
        invalid_days_rows = days_rows[1:] if first else days_rows[:-1]
        for days in invalid_days_rows:
            for day in days:
                del day.type.possible_types[T.Days]
                day.type.infer_type_from_neighbors()

    def of_type(self, typ: T, o: Orientation = V, single: bool = False,
                strict: bool = True) -> list[list[C]]:
        """ Return one or all series' of the given type.

        Each series will be partial in the sense
        that each cell will be of the given type.
        Thus, in general, the series is different
        from the row/col of the series' cells.

        :param typ: The type each cell in the returned row will have.
        :param o: The orientation the cells in the returned lists will have.
        :param single: Whether, only to return the first series encountered.
        :param strict: If type checking should be strict or not.
        :return: A list of lists,
            where each sublist contains cells of the given type.
        """
        cells_of_type: list[list[C]] = []
        for starter in self.get_series(o.normal, self.left):
            cells_of_type.append([])
            for cell in self.get_series(o, starter):
                if not cell.has_type(typ):
                    continue
                if not strict or cell.get_type() == typ:
                    cells_of_type[-1].append(cell)
            if not cells_of_type[-1]:
                cells_of_type.pop()
            # Only return cells of the first row/col
            # that contains cells of the given type.
            if single and cells_of_type:
                return cells_of_type
        return cells_of_type

    def merge_series(self, starter: C, d: Direction) -> None:
        """ Merge the row/col of the given cell to the neighboring series.

        :param starter: Used to get the series in the directions'
            orientations' normal orientation.
        :param d: The cells row/col will get merged to their respective
            neighbors in the given direction.
        """
        neighbor = starter.get_neighbor(d)
        if not neighbor:
            raise AssertionError(f"Can't merge in {d.name}. End of table.")
        o = d.default_orientation
        n = o.normal
        series = list(self.get_series(n, starter))
        neighbors = list(self.get_series(n, neighbor))
        for f1, f2 in zip(series, neighbors, strict=True):
            f1.merge(f2, ignore_neighbors=[n.lower, n.upper])

    def merge_stops(self) -> None:
        """ Merge consecutive cells of type stop. """
        def _merge_stops() -> bool:
            allow_merge = True
            stop: C | None = None
            for _, stop in stops:
                neighbor: C = stop.get_neighbor(n.upper)
                if not neighbor:
                    allow_merge = False
                    break
                if neighbor.get_type() not in [T.Stop, T.Empty]:
                    allow_merge = False
                    break
            if not stop or not allow_merge:
                return False
            series = "cols" if o == V else "rows"
            logger.info(f"Found two consecutive stop {series}. Merging...")
            self.merge_series(stop, n.upper)
            return True

        o, stops = self.find_stops()
        n = o.normal
        while _merge_stops():
            pass


def group_cells_by(cells: Iterable[C],
                   same_group_func: Callable[[C, C], bool],
                   pre_sort_keys: str | Iterable[str] | None,
                   group_sort_keys: str | Iterable[str] | None) -> list[Cs]:
    """ Group the given cells using the given function.

    :param cells: The cells that should be grouped.
    :param same_group_func: A function taking two cells and returning True,
      if they are in the same group, False otherwise.
    :param pre_sort_keys: Sort the cells before grouping using this as key.
    :param group_sort_keys: Each group will be sorted using this as key.
    :return: A list of groups of cells.
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
    """ Turns the datacells into a collection of columns. """
    def _same_col(cell1: C, cell2: C) -> bool:
        """ Two cells are in the same column if they overlap horizontally. """
        return not cell1.bbox.is_h_overlap(cell2.bbox)

    cols = group_cells_by(cells, _same_col, "bbox.x0", "bbox.y0")
    if link_cols:
        for col in cols:
            link_cells(S, col)
    return cols


def cells_to_rows(cells: Cs, *, link_rows: bool = True) -> list[Cs]:
    """ Turns the datacells into a collection of rows. """
    def _same_row(cell1: C, cell2: C) -> bool:
        """ Two cells are in the same row if they overlap vertically. """
        return not cell1.bbox.is_v_overlap(cell2.bbox)

    rows = group_cells_by(cells, _same_row, "bbox.y0", "bbox.x0")
    if link_rows:
        for row in rows:
            link_cells(E, row)
    return rows


def link_cells(d: Direction, cells: Cs) -> None:
    """ Link the fielsd in the given direction.

    The cells will be linked in the opposite direction implicitely.

    :param d: The direction to link in.
    :param cells: The cells that should be linked.
    """
    p = peekable(cells)
    for cell in p:
        cell.update_neighbor(d, p.peek(None))


def unlink_cells(d: Direction, cells: Cs) -> None:
    """ Remove the links to any other cells in the given direction.

    The links that are removed can be linking to arbitrary cells.

    :param d: The direction the cells' neighbors will be removed from.
    :param cells: The cells to remove the links from.
    """
    for cell in cells:
        cell.del_neighbor(d)


def link_rows_and_cols(rows: list[Cs], cols: list[Cs]) -> None:
    """ Link the rows and columns, such that each cell can be reached using
        any other cells and the cells' get_neighbor method.

    :param rows: The list of cells representing the rows.
    :param cols: The list of cells representing the cols.
    """
    # Fill first column.
    first_cell_of_rows = [row[0] for row in rows]
    head = insert_empty_cells_from_map(V, first_cell_of_rows, cols[0])
    cols[0] = list(head.iter(S))
    rel_col = cols[0]
    for col_id, col in enumerate(cols[1:], 1):
        head = insert_empty_cells_from_map(V, rel_col, col)
        cols[col_id] = list(head.iter(S))
        rel_col = cols[col_id]
    for col1, col2 in pairwise(cols):
        for f1, f2 in zip(col1, col2, strict=True):
            f1.del_neighbor(E)
            f2.del_neighbor(E)
            f1.set_neighbor(E, f2)
    for row_id, cell in enumerate(cols[0]):
        rows[row_id] = list(cell.iter(E, True))


def merge_small_cells(o: Orientation, ref_cells: Cs, cells: Cs) -> None:
    """ Merge cells, that are overlapping with the same ref_cell.

    Only the first overlapping cell is checked. That is, if a cell of cells
        is overlapping with multiple ref_cells, only the first one matters
        for the purpose of merging.
    If more than two cells are overlapping with the same ref_cell, they
        are all merged into a single cell.

    :param o: The orientation used to get the overlap.
    :param ref_cells: The cells used as reference.
    :param cells: The cells that might be merged.
    """
    if len(cells) < 2:
        return
    n = o.normal
    overlaps = {}
    first_ref_id = 0
    for cell in cells:
        cell_overlaps = []
        for i, ref_cell in enumerate(ref_cells[first_ref_id:], first_ref_id):
            bbox = ref_cell.table.get_bbox_of(
                ref_cell.table.get_series(o, ref_cell))
            if bbox.is_overlap(n.name.lower(), cell.bbox, 0.8):
                if not cell_overlaps:
                    first_ref_id = i
                cell_overlaps.append(ref_cell)
                continue
            if cell_overlaps:
                break
        overlaps[id(cell)] = cell_overlaps

    f1 = cells[0]
    f2 = cells[1]
    while f2:
        same_overlap = any([o2 in overlaps[id(f1)] for o2 in overlaps[id(f2)]])
        if not same_overlap:
            f1 = f2
            f2 = f2.get_neighbor(n.upper)
            continue
        f1.merge(f2)
        cells.remove(f2)
        # f1 has all neighbors of f2 after merge.
        f2 = f1.get_neighbor(n.upper)


def insert_empty_cells_from_map(
        o: Orientation, ref_cells: Cs, cells: Cs) -> C:
    """ Insert EmptyFields as neighbors of the cells, until cells and
    ref_cells can be mapped (i.e. can be neighbors)

    :param o: V or H. If V, ref_cells should be a column of a table;
        if H, a row instead.
    :param ref_cells: The cells used as reference.
    :param cells: The cells that are used as starting point. All of these
        will be part of the linked cell list.
    :return: The (possibly new, empty) first cell.
    """
    # Add cells at the start and between other cells.
    i = 0
    cell_count = 0
    for ref_cell in ref_cells:
        if i >= len(cells):
            break
        cell_count += 1
        cell = cells[i]
        if ref_cell.is_overlap(o, cell, 0.8):
            i += 1
            continue
        e = EmptyCell()
        if o == H:
            e.set_bbox_from_reference_cells(ref_cell, cell)
        else:
            e.set_bbox_from_reference_cells(cell, ref_cell)

        cell.set_neighbor(o.lower, e)

    # Add empty nodes at the end.
    cell = cells[-1]
    while cell_count < len(ref_cells):
        e = EmptyCell()
        ref_cell = ref_cells[cell_count]
        if o == H:
            e.set_bbox_from_reference_cells(ref_cell, cell)
        else:
            e.set_bbox_from_reference_cells(cell, ref_cell)
        cell.set_neighbor(o.upper, e)
        cell_count += 1
        cell = e

    # Return head
    cell = cells[0]
    while cell.has_neighbors(d=o.lower):
        cell = cell.get_neighbor(o.lower)
    return cell


def replace_cell(which: C, replace_with: C) -> None:
    """ Replace one cell with the other.

    :param which: The cell that will be replaced.
    :param replace_with: The cell that will be inserted instead.
    """
    # New node should not have any neighbors
    assert not replace_with.has_neighbors(o=V)
    assert not replace_with.has_neighbors(o=H)
    for d in D:
        neighbor = which.get_neighbor(d)
        if not neighbor:
            continue
        which.del_neighbor(d)
        neighbor.set_neighbor(d.opposite, replace_with)
    which.table = None


def insert_cells_in_col(col: Cs, cells: Cs) -> None:
    """ Insert the cells into the given col, replacing existing cells.

    :param col: The column the cells are inserted into.
    :param cells: The cells that will be inserted into the column.
    """
    last_id = 0
    for cell in cells:
        for i, col_cell in enumerate(col[last_id:], last_id):
            if not col_cell.is_overlap(V, cell, 0.8):
                continue
            assert col_cell.is_overlap(H, cell, 0.8)
            replace_cell(col_cell, cell)
            last_id = i + 1
            break
