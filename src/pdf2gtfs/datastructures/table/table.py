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
from pdf2gtfs.datastructures.table.bounds import select_adjacent_fields
from pdf2gtfs.datastructures.table.fields import (
    EmptyField, F, Fs, OF,
    )
from pdf2gtfs.datastructures.table.fieldtype import T
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
    def __init__(self, first_node: F, last_node: F):
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
        for row_field in self.top.row:
            for col_field in row_field.col:
                col_field.table = self
        self._get_bbox_call_count: int = 0
        self.other_fields = None

    @property
    def top(self) -> OF:
        """ One of the nodes in the top row. """
        return self.get_end_node(d=N)

    @property
    def left(self) -> OF:
        """ One of the nodes in the left-most column. """
        return self.get_end_node(d=W)

    @property
    def bot(self) -> OF:
        """ One of the nodes in the bottom column. """
        return self.get_end_node(d=S)

    @property
    def right(self) -> OF:
        """ One of the nodes in the right-most column. """
        return self.get_end_node(d=E)

    @property
    def bbox(self) -> BBox:
        """ The bbox, that contains every field of the table. """
        # TODO NOW: This is not entirely true. It should be using
        #  the col and row for all end nodes.
        return self.get_bbox_of([self.left, self.right])

    @staticmethod
    def from_fields(fields: Fs) -> Table:
        """ Create a new table from the given fields.

        :param fields:
        :return:
        """
        cols = fields_to_cols(fields)
        rows = fields_to_rows(fields)
        link_rows_and_cols(rows, cols)
        t = Table(cols[0][0], rows[-1][-1])
        return t

    def get_end_node(self, d: Direction) -> OF:
        """ Return one of the end nodes in the given direction.

        :param d: The direction to look for the end node in.
        """
        # Get the current end node.
        node: OF = getattr(self, d.p_end)
        o = d.default_orientation
        d2 = o.normal.lower if d == o.lower else o.normal.upper
        if not node.has_neighbors(d=d) and not node.has_neighbors(d=d2):
            return node

        self._update_end_node(d, node)
        return self.get_end_node(d)

    def _set_end_node(self, d: Direction, node: OF) -> None:
        """ Store the last node in the given direction to node.

        This will fail if node has a neighbor in the given direction.

        :param d: The direction, which specifies, where to store the node.
        :param node: The node to be stored.
        """
        assert node.get_neighbor(d) is None
        setattr(self, d.p_end, node)

    def _update_end_node(self, d: Direction, start: F) -> None:
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
        node = self.get_first(d, start)
        d2 = o.normal.lower if d == o.lower else o.normal.upper
        node = self.get_first(d2, node)
        self._set_end_node(d, node)

    def get_first(self, d: Direction, node: F) -> F:
        """ Return the final node in the given direction, starting at node.

        :param d: The direction to get the final node in.
        :param node: The node to start the search at.
        :return: Either node, if it is the last node or a node that is an
            extended neighbor (i.e. neighbor/neighbors neighbor/...).
        """
        while node.has_neighbors(d=d):
            node = node.get_neighbor(d)
        return node

    def get_list(self, o: Orientation, node: OF = None) -> list[F]:
        """ Return the full list of nodes in the given orientation.

        :param o: The orientation the nodes will be in.
        :param node: The node used to get a specific row/column. If set to
         None, the first/top node will be used instead.
        """
        if not node:
            node = self.get_end_node(o.lower)
        return list(self.iter(o.upper, node))

    def insert(self, d: Direction, rel_node: OF, new_node: F) -> None:
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

    def get_series(self, o: Orientation, node: F) -> Generator[F]:
        """ The row or column the node resides in.

        :param o: The orientation of the series, i.e. whether to return
            row (H) or column (V).
        :param node: The node in question.
        :return: A generator that yields all objects in the series.
        """
        return self.iter(o.upper, node)

    def get_bbox_of(self, nodes: Iterator[F]) -> BBox:
        """ Return the combined bbox of nodes.

        Also caches the results, in case the same bbox is requested again.

        :param nodes: The nodes to get the bbox from.
        :return: A bbox, that contains all the nodes' bboxes.
        """
        # Allow only a single recursive call.
        # This will prevent Table.bbox from producing the wrong result,
        # if at least one of the nodes used to calculate it is an EmptyField.
        recursion_depth = 1
        # Changing the depth to 0 will cause tests to fail.
        # Changing it to anything higher than 1 will decrease performance
        #  by orders of magnitude.
        if self._get_bbox_call_count > recursion_depth:
            raise RecursionError
        self._get_bbox_call_count += 1
        bboxes = []
        for node in nodes:
            try:
                bboxes.append(node.bbox)
            except RecursionError:
                pass
        self._get_bbox_call_count -= 1
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

    def iter(self, d: Direction, node: OF = None) -> Generator[F]:
        """ Start on the opposite end of d and iterate over nodes towards d.

        :param d: The direction to iterate towards to.
        :param node: If given, the generator will yield nodes of the
            col/row of node, based on d. Otherwise, always yield the
            first col/row.
        :return: An iterator over the nodes.
        """
        node = self.get_first(d.opposite, node)
        while node:
            yield node
            node = node.get_neighbor(d)

    def get_empty_field_bbox(self, field: EmptyField) -> BBox:
        """ The bbox of an empty field is defined as its row's x-coordinates
        and its col's y-coordinates.

        :param field: The EmptyField the bbox was requested for.
        :return: A bbox, that is contained by both the row/col, while having
            the row's height and the col's width.
        """
        row_bbox = self.get_bbox_of(field.row)
        col_bbox = self.get_bbox_of(field.col)
        return BBox(col_bbox.x0, row_bbox.y0, col_bbox.x1, row_bbox.y1)

    def expand(self, d: Direction) -> bool:
        """ Expand the table in the given direction using the given fields.

        :param d: The direction the expansion is done towards.
        :return: Whether any fields were added.
        """
        if self.other_fields is None:
            raise Exception("Other fields need to be added to this table,"
                            "before trying to expand.")
        normal = d.default_orientation.normal
        ref_fields = list(self.get_series(normal, self.get_end_node(d)))

        bboxes = [self.get_bbox_of(self.get_series(d.default_orientation, f))
                  for f in ref_fields]
        adjacent_fields = select_adjacent_fields(d, bboxes, self.other_fields)
        if not adjacent_fields:
            return False

        link_nodes(normal.upper, adjacent_fields)
        merge_small_fields(d.default_orientation, ref_fields, adjacent_fields)

        head = insert_empty_fields_from_map(
            normal, ref_fields, adjacent_fields)
        try:
            self.insert(d, ref_fields[0], head)
        except ValueError:
            # Insertion has failed. This usually (hopefully) means that the
            # adjacent fields are not part of the table.
            unlink_nodes(d, ref_fields)
            return False
        # Only remove fields that were added.
        for field in adjacent_fields:
            self.other_fields.remove(field)
        return True

    def get_contained_fields(self, fields: Fs) -> Fs:
        """ Get all fields, that are within the tables' fields' combined bbox.

        :param fields: The fields that might be contained by the table.
        :return: A list of all fields of the given fields, that have a bbox
            that is contained in the tables bbox.
        """
        def _both_overlap(field: F) -> bool:
            return (bbox.is_v_overlap(field.bbox, 0.8) and
                    bbox.is_h_overlap(field.bbox, 0.8))

        bbox = BBox.from_bboxes(
            [self.get_bbox_of(self.left.col),
             self.get_bbox_of(self.right.col),
             self.get_bbox_of(self.top.row),
             self.get_bbox_of(self.bot.row)])

        fields = list(filter(_both_overlap, fields))
        return fields

    def get_containing_col(self, field: F) -> Fs | None:
        """ Find the column that contains (via bbox-overlap) the field.

        :param field: The field, we want to know the column of.
        :return: The column, that contains the field or None if no
            such column exists.
        """
        for col_field in self.left.iter(E):
            if col_field.is_overlap(H, field, 0.8):
                return list(col_field.col)
        return None

    def get_col_left_of(self, field: F) -> Fs:
        """ Get the last column left of the field.

        That is, the column right of whichever column this function returns
        (if any) either contains the field or is located right of the field.

        :param field: The field we are using as reference.
        :return: The last column left of the field or None, if no such
         column exists.
        """
        def _is_right_of_field(f: F) -> bool:
            return f.bbox.x0 >= left_most_field.bbox.x0

        if field.table == self:
            return field.prev.col

        top_field = field
        while top_field.above:
            top_field = top_field.above

        left_most_field = min(top_field.iter(S), key=attrgetter("bbox.x0"))
        col_right_of_field = first_true(
            self.left.row, default=self.left, pred=_is_right_of_field)
        # TODO NOW: Will fail if default.
        return col_right_of_field.prev.col

    def insert_repeat_fields(self, fields: Fs) -> None:
        """ Find the fields that are part of a repeat interval and add
            them to the table.

        :param fields: The fields that are checked for repeat intervals.
        """
        identifiers = self.get_repeat_identifiers(fields)
        if not identifiers:
            return
        values = self.get_repeat_values(identifiers, fields)
        for field in identifiers + values:
            fields.remove(field)
        # Add identifiers and their values to table.
        # Group repeat fields by col and link them.
        repeat_groups = fields_to_cols(identifiers + values)
        # Insert the repeat_groups each into a new or existing column.
        for group in repeat_groups:
            col = self.get_containing_col(group[0])
            if col:
                unlink_nodes(S, group)
                insert_fields_in_col(col, group)
                continue
            col = self.get_col_left_of(group[0])
            head = insert_empty_fields_from_map(V, col, group)
            self.insert(E, col[0], head)

    def get_repeat_identifiers(self, fields: Fs) -> Fs:
        """ Return those fields, that are repeat identifiers.

        :param fields: The fields that may be identifiers.
        :return: Those fields that are repeat identifiers.
        """
        contained_fields = self.get_contained_fields(fields)
        repeat_identifiers = [f for f in contained_fields
                              if f.has_type(T.RepeatIdent)]
        if repeat_identifiers:
            fields_to_cols(repeat_identifiers)
        return repeat_identifiers

    def get_repeat_values(self, identifiers: Fs, fields: Fs) -> Fs:
        """ Given the identifiers, find those fields that are repeat values.

        :param identifiers: The repeat identifiers.
        :param fields: The fields that are evaluated.
        :return: Those fields that are repeat values.
        """
        contained_fields = self.get_contained_fields(fields)
        values = []
        repeat_groups = fields_to_cols(identifiers + values, link_cols=False)
        for group in repeat_groups:
            for i1, i2 in pairwise(group):
                overlaps = [f for f in contained_fields
                            if f.is_overlap(H, i1, 0.8)
                            and f.has_type(T.RepeatValue)]
                # Only a single value is needed/possible.
                for value in overlaps:
                    if i1.bbox.y0 < value.bbox.y0 < i2.bbox.y0:
                        values.append(value)
                        break
        return values

    def _print(self, getter_func: Callable[[F], str],
               align_func: Callable[[F], str] = lambda _: "^",
               col_count: int | None = None) -> None:
        rows = [field.row for field in self.left.col]
        cols = [field.col for field in self.top.row]
        # The maximum length of a fields text in each column.
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
            """ Right align all data fields; left align everything else.
            :param f: This fields text is checked.
            :return: The format char used for alignment.
            """
            return ">" if f.get_type() == T.Data else "<"

        self._print(attrgetter("text"), get_text_align, col_count)

    def print_types(self, col_count: int = None) -> None:
        """ Print the inferred type of each field, instead of its text. """
        def _get_type_name(f: F) -> str:
            if isinstance(f, EmptyField):
                return ""
            return f.get_type().name

        self._print(_get_type_name, col_count=col_count)

    def split_at_fields(self, o: Orientation, splitter: list[Fs]
                        ) -> list[Table]:
        """ Split the table at the given fields.

        :param o: The orientation to split in.
        :param splitter: The fields used to split the table.
        :return: A list of tables, where each table contains only fields,
            that are between the given splitter.
        """
        if not splitter:
            return [self]
        table_fields = self._split_at_splitter(o, splitter)

        tables = []
        for table_field in table_fields:
            head = table_field[0]
            # The splitter should not implicitly be part of the table.
            if head.table != self:
                continue
            field = None
            # Unlink last row/col of each table, based on o.
            for field in self.get_series(o, table_field[-1]):
                field.set_neighbor(o.normal.upper, None)
            table = Table(head, field)
            table.remove_empty_series()
            tables.append(table)

        return tables

    def _get_splitting_series(self, o: Orientation, grouped_fields: list[Fs]
                              ) -> list[Fs]:
        splitter = []
        idx = 0
        n = o.normal
        table_fields = list(self.get_series(n, self.get_end_node(n.upper)))
        bound = "y0" if o == H else "x0"
        for group in grouped_fields:
            group_bbox = BBox.from_bboxes([f.bbox for f in group])
            for i, table_field in enumerate(table_fields[idx:], idx):
                table_bbox = self.get_bbox_of(self.get_series(o, table_field))
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

    def get_splitting_cols(self, contained_fields: Fs) -> list[Fs]:
        """ Return those fields, that split the table vertically,
            i.e. none of these fields fit in any column of the table.

        :param contained_fields: The fields to check. All of these should be
            contained in the table.
        :return: The fields that split the table vertically.
        """
        cols = fields_to_cols(contained_fields, link_cols=False)
        splitter = self._get_splitting_series(V, cols)
        return splitter

    def get_splitting_rows(self, contained_fields: Fs) -> list[Fs]:
        """ Get the fields that split the table horizontally,
            i.e. none of these fields fit in any row of the table.

        :param contained_fields: The fields to check. All of these should
            be contained in the table.
        :return: The fields that split the table horizontally.
        """
        rows = fields_to_rows(contained_fields, link_rows=False)
        splitter = self._get_splitting_series(H, rows)
        return splitter

    def max_split(self, fields: Fs) -> list[Table]:
        """ Split the table horizontally (if appliccable) using the given
            fields and then split each of those vertically (if appliccable).

        The current table should not be used after it was split.

        :param fields: The fields that may split the table in either direction.
        :return: The list of tables.
        """
        contained_fields = self.get_contained_fields(fields)
        if not contained_fields:
            return [self]
        col_splitter = self.get_splitting_cols(contained_fields)
        row_splitter = self.get_splitting_rows(contained_fields)

        col_tables = self.split_at_fields(V, col_splitter)
        tables = []
        for table in col_tables:
            tables += table.split_at_fields(H, row_splitter)

        return list(collapse(tables))

    def _split_at_splitter(self, o: Orientation, splitter: list[Fs]
                           ) -> list[Fs]:
        def _same_table(field1: F, field2: F) -> bool:
            return field1.table != field2.table

        fields = list(self.get_series(o.normal, self.get_end_node(o.lower)))
        fields += list(collapse(splitter))
        pre_sorter = "bbox.y0" if o == H else "bbox.x0"
        return group_fields_by(fields, _same_table, pre_sorter, None)

    def _remove_empty_series(self, o: Orientation) -> None:
        n = o.normal
        for field in list(self.get_series(o, self.top)):
            series = list(self.get_series(n, field))
            if any((not isinstance(f, EmptyField) for f in series)):
                continue
            lower_neighbor = series[0].get_neighbor(o.lower)
            upper_neighbor = series[0].get_neighbor(o.upper)
            unlink_nodes(o.lower, series)
            unlink_nodes(o.upper, series)
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
        from pdf2gtfs.datastructures.timetable.table import TimeTable
        from pdf2gtfs.datastructures.timetable.stops import Stop
        from pdf2gtfs.datastructures.timetable.entries import (
            TimeTableEntry, TimeTableRepeatEntry, Weekdays,
            )

        def add_field_to_timetable() -> None:
            match field.get_type():
                case T.Other | T.Empty | T.Stop:
                    return
                case T.Data:
                    stop = t.stops.get_from_id(stop_id)
                    entries[e_id].set_value(stop, field.text)
                    non_empty_entries.add(e_id)
                case T.EntryAnnotValue:
                    annots = set([a.strip() for a in field.text.split()])
                    entries[e_id].annotations = annots
                case T.Days:
                    entries[e_id].days = Weekdays(field.text)
                case T.RouteAnnotValue:
                    entries[e_id].route_name = field.text
                case T.StopAnnot:
                    stop = t.stops.get_from_id(stop_id)
                    t.stops.add_annotation(field.text, stop=stop)
                case T.RepeatValue:
                    e = entries[e_id]
                    if not isinstance(entries[e_id], TimeTableRepeatEntry):
                        entries[e_id] = TimeTableRepeatEntry(
                            "", [field.text])
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
            for e_id, field in enumerate(self.get_series(n, start)):
                add_field_to_timetable()

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

    def find_stops(self) -> tuple[Orientation, list[tuple[int, F]]]:
        """ Get the row/column, that contains the stops.

        :return: The orientation of the stops, as well as the list of
            stops, with each stop's row/col index based on orientation.
        """
        def _find_stops(o: Orientation, start: F | None = None
                        ) -> list[tuple[int, F]]:
            for field in self.get_series(o.normal, start or self.left):
                series = [(i, f)
                          for i, f in enumerate(self.get_series(o, field))
                          if f.get_type() == T.Stop]
                if not series:
                    continue
                return series
            return []

        v_stops = _find_stops(V)
        h_stops = _find_stops(H)
        return (V, v_stops) if len(v_stops) > len(h_stops) else (H, h_stops)

    def expand_all(self, all_directions: bool = False) -> None:
        expanded = True
        while expanded:
            expanded = False
            for d in D:
                if not all_directions and d in [S, E]:
                    continue
                expanded |= self.expand(d)

    def infer_field_types(self, first_table: Table | None) -> None:
        # TODO: Test if it makes a difference, running this twice.
        for starter in self.left.row:
            for field in starter.col:
                field.type.infer_type_from_neighbors()
        for starter in self.left.row:
            for field in starter.col:
                field.type.infer_type_from_neighbors()
        self.merge_stops()

        if first_table is None:
            return
        # Use the first table on the page to determine, which days row/col
        # is the correct one, in case multiple days rows or cols exist.
        days_rows = self.of_type(T.Days, H)
        first_days_row = first_table.of_type(T.Days, H, single=True)[0]
        if not days_rows:
            # Duplicate -> add to self.
            for day in first_days_row:
                self.other_fields.append(day.duplicate())
            self.expand_all()
            return
        if len(days_rows) == 1:
            return
        first_table_col = list(first_days_row[0].col)
        first_days_row_idx = first_table_col.index(first_days_row[0])
        first = first_days_row_idx < len(first_table_col) / 2
        first_or_last = "first" if first else "last"
        logger.info("Found multiple rows containing fields of type Days for "
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
                strict: bool = True) -> list[list[F]]:
        fields_of_type: list[list[F]] = []
        for starter in self.get_series(o.normal, self.left):
            fields_of_type.append([])
            for field in self.get_series(o, starter):
                if not field.has_type(typ):
                    continue
                if not strict or field.get_type() == typ:
                    fields_of_type[-1].append(field)
            if not fields_of_type[-1]:
                fields_of_type.pop()
            # Only return fields of the first row/col
            # that contains fields of the given type.
            if single and fields_of_type:
                return fields_of_type
        return fields_of_type

    def merge_series(self, starter: F, d: Direction) -> None:
        neighbor = starter.get_neighbor(d)
        if not neighbor:
            raise AssertionError(f"Can't merge in {d.name}. End of table.")
        o = d.default_orientation
        n = o.normal
        series = list(self.get_series(n, starter))
        neighbors = list(self.get_series(n, neighbor))
        for f1, f2 in zip(series, neighbors, strict=True):
            f1.merge(f2, ignore=[n.lower, n.upper])

    def merge_stops(self) -> None:
        def _merge_stops() -> bool:
            allow_merge = True
            stop: F | None = None
            for _, stop in stops:
                neighbor: F = stop.get_neighbor(n.upper)
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


def group_fields_by(fields: Iterable[F],
                    same_group_func: Callable[[F, F], bool],
                    pre_sort_keys: str | Iterable[str] | None,
                    group_sort_keys: str | Iterable[str] | None) -> list[Fs]:
    """ Group the given fields using the given function.

    :param fields: The fields that should be grouped.
    :param same_group_func: A function taking two fields and returning True,
      if they are in the same group, False otherwise.
    :param pre_sort_keys: Sort the fields before grouping using this as key.
    :param group_sort_keys: Each group will be sorted using this as key.
    :return: A list of groups of fields.
    """
    groups: list[Fs] = []
    if pre_sort_keys:
        pre_sorter = attrgetter(*always_iterable(pre_sort_keys))
        fields = sorted(fields, key=pre_sorter)

    group_sorter = None
    if group_sort_keys:
        group_sorter = attrgetter(*always_iterable(group_sort_keys))
    for group in split_when(fields, same_group_func):
        if group_sorter:
            group.sort(key=group_sorter)
        groups.append(group)

    return groups


def fields_to_cols(fields: Fs, *, link_cols: bool = True) -> list[Fs]:
    """ Turns the datafields into a collection of columns. """
    def _same_col(field1: F, field2: F) -> bool:
        """ Two fields are in the same column if they overlap horizontally. """
        return not field1.bbox.is_h_overlap(field2.bbox)

    cols = group_fields_by(fields, _same_col, "bbox.x0", "bbox.y0")
    if link_cols:
        for col in cols:
            link_nodes(S, col)
    return cols


def fields_to_rows(fields: Fs, *, link_rows: bool = True) -> list[Fs]:
    """ Turns the datafields into a collection of rows. """
    def _same_row(field1: F, field2: F) -> bool:
        """ Two fields are in the same row if they overlap vertically. """
        return not field1.bbox.is_v_overlap(field2.bbox)

    rows = group_fields_by(fields, _same_row, "bbox.y0", "bbox.x0")
    if link_rows:
        for row in rows:
            link_nodes(E, row)
    return rows


def link_nodes(d: Direction, fields: Fs) -> None:
    """ Link the fielsd in the given direction.

    The fields will be linked in the opposite direction implicitely.

    :param d: The direction to link in.
    :param fields: The fields that should be linked.
    """
    p = peekable(fields)
    for field in p:
        field.set_neighbor(d, p.peek(None))


def unlink_nodes(d: Direction, fields: Fs) -> None:
    """ Remove the links to any other fields in the given direction.

    The links that are removed can be linking to arbitrary fields.

    :param d: The direction the fields' neighbors will be removed from.
    :param fields: The fields to remove the links from.
    """
    for field in fields:
        field.set_neighbor(d, None)


def link_rows_and_cols(rows: list[Fs], cols: list[Fs]) -> None:
    """ Link the rows and columns, such that each field can be reached using
        any other fields and the fields' get_neighbor method.

    :param rows: The list of fields representing the rows.
    :param cols: The list of fields representing the cols.
    """
    # Fill first column.
    first_field_of_rows = [row[0] for row in rows]
    head = insert_empty_fields_from_map(V, first_field_of_rows, cols[0])
    cols[0] = list(head.iter(S))
    rel_col = cols[0]
    for col_id, col in enumerate(cols[1:], 1):
        head = insert_empty_fields_from_map(V, rel_col, col)
        cols[col_id] = list(head.iter(S))
        rel_col = cols[col_id]
    for col1, col2 in pairwise(cols):
        for f1, f2 in zip(col1, col2, strict=True):
            f1.set_neighbor(E, None)
            f2.set_neighbor(E, None)
            f1.set_neighbor(E, f2)
    for row_id, field in enumerate(cols[0]):
        rows[row_id] = list(field.iter(E))


def merge_small_fields(o: Orientation, ref_fields: Fs, fields: Fs) -> None:
    """ Merge fields, that are overlapping with the same ref_field.

    Only the first overlapping field is checked. That is, if a field of fields
        is overlapping with multiple ref_fields, only the first one matters
        for the purpose of merging.
    If more than two fields are overlapping with the same ref_field, they
        are all merged into a single field.

    :param o: The orientation used to get the overlap.
    :param ref_fields: The fields used as reference.
    :param fields: The fields that might be merged.
    """
    if len(fields) < 2:
        return
    n = o.normal
    overlaps = {}
    first_ref_id = 0
    for field in fields:
        field_overlaps = []
        for i, ref_field in enumerate(ref_fields[first_ref_id:], first_ref_id):
            bbox = ref_field.table.get_bbox_of(
                ref_field.table.get_series(o, ref_field))
            if bbox.is_overlap(n.name.lower(), field.bbox, 0.8):
                if not field_overlaps:
                    first_ref_id = i
                field_overlaps.append(ref_field)
                continue
            if field_overlaps:
                break
        overlaps[id(field)] = field_overlaps

    f1 = fields[0]
    f2 = fields[1]
    while f2:
        same_overlap = any([o2 in overlaps[id(f1)] for o2 in overlaps[id(f2)]])
        if not same_overlap:
            f1 = f2
            f2 = f2.get_neighbor(n.upper)
            continue
        f1.merge(f2)
        fields.remove(f2)
        # f1 has all neighbors of f2 after merge.
        f2 = f1.get_neighbor(n.upper)


def insert_empty_fields_from_map(
        o: Orientation, ref_fields: Fs, fields: Fs) -> F:
    """ Insert EmptyFields as neighbors of the fields, until fields and
    ref_fields can be mapped (i.e. can be neighbors)

    :param o: V or H. If V, ref_fields should be a column of a table;
        if H, a row instead.
    :param ref_fields: The fields used as reference.
    :param fields: The fields that are used as starting point. All of these
        will be part of the linked field list.
    :return: The (possibly new, empty) first field.
    """
    # Add fields at the start and between other fields.
    i = 0
    field_count = 0
    for ref_field in ref_fields:
        if i >= len(fields):
            break
        field_count += 1
        field = fields[i]
        if ref_field.is_overlap(o, field, 0.8):
            i += 1
            continue
        e = EmptyField()
        if o == H:
            e.set_bbox_from_reference_fields(ref_field, field)
        else:
            e.set_bbox_from_reference_fields(field, ref_field)

        field.set_neighbor(o.lower, e)

    # Add empty nodes at the end.
    field = fields[-1]
    while field_count < len(ref_fields):
        e = EmptyField()
        ref_field = ref_fields[field_count]
        if o == H:
            e.set_bbox_from_reference_fields(ref_field, field)
        else:
            e.set_bbox_from_reference_fields(field, ref_field)
        field.set_neighbor(o.upper, e)
        field_count += 1
        field = e

    # Return head
    field = fields[0]
    while field.has_neighbors(d=o.lower):
        field = field.get_neighbor(o.lower)
    return field


def replace_field(which: F, replace_with: F) -> None:
    """ Replace one field by the other.

    :param which: The field that will be replaced.
    :param replace_with: The field that will be inserted instead.
    """
    # New node should not have any neighbors
    assert not replace_with.has_neighbors(o=V)
    assert not replace_with.has_neighbors(o=H)
    for d in D:
        neighbor = which.get_neighbor(d)
        if not neighbor:
            continue
        which.set_neighbor(d, None)
        neighbor.set_neighbor(d.opposite, replace_with)
    which.table = None


def insert_fields_in_col(col: Fs, fields: Fs) -> None:
    """ Insert the fields into the given col, replacing existing fields.

    :param col: The column the fields are inserted into.
    :param fields: The fields that will be inserted into the column.
    """
    last_id = 0
    for field in fields:
        for i, col_field in enumerate(col[last_id:], last_id):
            if not col_field.is_overlap(V, field, 0.8):
                continue
            assert col_field.is_overlap(H, field, 0.8)
            replace_field(col_field, field)
            last_id = i + 1
            break
