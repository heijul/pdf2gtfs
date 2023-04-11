from __future__ import annotations

from itertools import pairwise
from operator import attrgetter
from typing import Callable, TypeVar

from more_itertools import peekable, split_before, spy

from pdf2gtfs.datastructures.pdftable.bbox import BBox
from pdf2gtfs.datastructures.table.bounds import select_adjacent_fields
from pdf2gtfs.datastructures.table.fields import (
    EmptyDataField, EmptyField, F, Fs, OF,
    )
from pdf2gtfs.datastructures.table.quadlinkedlist import (
    QuadLinkedList,
    )
from pdf2gtfs.datastructures.table.direction import (
    Direction, E, H, N, Orientation, S, V, W,
    )


Col = TypeVar("Col")
Row = TypeVar("Row")
Cols = TypeVar("Cols")
Rows = TypeVar("Rows")


class Table(QuadLinkedList[F, OF]):
    def __init__(self, first_node: F, last_node: F):
        super().__init__(first_node, last_node)

    @staticmethod
    def from_fields(fields: Fs) -> Table:
        """ Create a new table from the given fields.

        :param fields:
        :return:
        """
        cols = datafields_to_cols(fields)
        rows = datafields_to_rows(fields)
        insert_missing_empty_fields(rows, cols)
        t = Table(cols[0][0], rows[-1][-1])
        return t

    def get_empty_field_bbox(self, node: EmptyField) -> BBox:
        row_bbox = self.get_bbox_of(self.row(node))
        col_bbox = self.get_bbox_of(self.col(node))
        return BBox(col_bbox.x0, row_bbox.y0, col_bbox.x1, row_bbox.y1)

    def insert_empty_fields_from_map(
            self, o: Orientation, ref_fields: Fs, fields: Fs) -> F:
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
            field.set_neighbor(o.lower, e)

        # Add empty nodes at the end.
        while field_count < len(ref_fields):
            e = EmptyField()
            fields[-1].set_neighbor(o.upper, e)
            field_count += 1

        field = fields[0]
        while True:
            if not field.get_neighbor(o.lower):
                return field
            field = field.get_neighbor(o.lower)

    def expand(self, d: Direction, fields: Fs) -> bool:
        normal = d.default_orientation.normal
        ref_fields = list(self.iter(normal.upper, self.get_end_node(d)))
        adjacent_fields = select_adjacent_fields(d, ref_fields, fields)
        if not adjacent_fields:
            return False

        # Merge adjacent fields, that are overlapping with the same ref_field.
        merged = []
        for ref_field in ref_fields:
            for f1, f2 in pairwise(adjacent_fields):
                if not ref_field.is_overlap(normal, f1):
                    continue
                if ref_field.is_overlap(normal, f2):
                    f1.bbox.merge(f2.bbox)
                    f1.chars += f2.chars
                    f1.text += f" {f2.text}"
                    merged.append(f2)
        for field in merged:
            adjacent_fields.remove(field)

        link_nodes(normal.upper, adjacent_fields)
        head = self.insert_empty_fields_from_map(
            normal, ref_fields, adjacent_fields)
        self.insert(d, ref_fields[0], head)

    def expand_west(self, fields: Fs) -> bool:
        return self.expand(W, fields)

    def expand_east(self, fields: Fs) -> bool:
        return self.expand(E, fields)

    def expand_north(self, fields: Fs) -> bool:
        return self.expand(N, fields)

    def expand_south(self, fields: Fs) -> bool:
        return self.expand(S, fields)

    def print(self) -> None:
        first_column = self.get_list(V, self.left)
        rows = [self.get_list(H, field) for field in first_column]
        delim = " | "
        lines = []
        for row in rows:
            lines += [delim.lstrip()
                      + delim.join([f"{f.text: >5}" for f in row])
                      + delim.rstrip()]

        print("\n".join(lines))


def group_fields_by(fields: Fs, func: Callable[[F, F], bool],
                    pre_sorter: str, group_sorter: str) -> list[Fs]:
    """ Group the given fields using the given function.

    :param fields: The fields that should be grouped.
    :param func: A function taking two fields and returning, whether they
     are in the same group.
    :param pre_sorter: Sort the fields before grouping using this as key.
    :param group_sorter: Each group will be sorted using this as key.
    :return: A list of groups of fields.
    """
    def splitter_func(field: F) -> bool:
        """ Wraps func, so it can be used in split_before.

        :param field: The field used, to decide whether to split.
        :return: Whether to split.
        """
        return func(f, field)

    groups: list[Fs] = []
    p = peekable(sorted(fields, key=attrgetter(pre_sorter)))
    f = p.peek()
    for group in split_before(p, splitter_func):
        groups.append(sorted(group, key=attrgetter(group_sorter)))
        f = p.peek(None)
        if f is None:
            break

    return groups


def datafields_to_cols(data_fields: Fs) -> Cols:
    """ Turns the datafields into a collection of columns. """
    def _group_func(field1: F, field2: F) -> bool:
        """ Two fields are in the same column if they overlap horizontally. """
        return not field1.bbox.is_h_overlap(field2.bbox)

    cols = group_fields_by(data_fields, _group_func, "bbox.x0", "bbox.y0")
    for col in cols:
        link_nodes(S, col)
    return cols


def datafields_to_rows(data_fields: Fs) -> Rows:
    """ Turns the datafields into a collection of rows. """
    def _group_func(field1: F, field2: F) -> bool:
        """ Two fields are in the same row if they overlap vertically. """
        return not field1.bbox.is_v_overlap(field2.bbox)

    data_fields = sorted(data_fields, key=attrgetter("bbox.y0"))
    rows = group_fields_by(data_fields, _group_func, "bbox.y0", "bbox.x0")
    for row in rows:
        link_nodes(E, row)
    return rows


def link_nodes(d: Direction, fields: Fs) -> None:
    p = peekable(fields)
    for field in p:
        field.set_neighbor(d, p.peek(None))


def insert_missing_empty_fields(rows: list[Fs], cols: list[Fs]) -> None:
    # Fill first column.
    first_field_of_rows = [row[0] for row in rows]
    (first_col,), cols = spy(cols)
    row_id = 0
    for field in first_col:
        while field != first_field_of_rows[row_id]:
            empty_field = EmptyDataField()
            field.below = empty_field
            first_field_of_rows[row_id].prev = empty_field
            row_id += 1
        row_id += 1
    cols_top = [col[0] for col in cols]
    new_tops = {}
    for field1, field2 in pairwise(cols_top):
        field1 = new_tops.get(field1, field1)
        field2 = new_tops.get(field2, field2)
        new_field2 = insert_missing_fields_in_adjacent_col(field1, field2)
        if field2 == new_field2:
            continue
        new_tops[field2] = new_field2


def insert_missing_fields_in_adjacent_col_in_direction(
        d: Direction, head1: F, head2: F, update_neighbor_in_d: bool = False
        ) -> F:
    o = d.default_orientation
    on = o.normal
    col1 = list(head1.iter(on.upper))
    col2 = list(head2.iter(on.upper))
    for i in range(len(col1)):
        if i < len(col2) and col1[i].get_neighbor(d) == col2[i]:
            if i > 0 and col2[i - 1].get_neighbor(on.lower) != col2[i]:
                col2[i].set_neighbor(on.lower, col2[i - 1])
            continue
        empty_field = EmptyDataField()
        col1[i].set_neighbor(d, empty_field)
        if i > 0:
            col2[i - 1].set_neighbor(on.upper, empty_field)
        col2.insert(i, empty_field)

    while True:
        if not head2.get_neighbor(on.lower):
            return head2
        head2 = head2.get_neighbor(on.lower)


def insert_missing_fields_in_adjacent_col(head1: F, head2: F) -> F:
    col1 = list(head1.iter(S))
    col2 = list(head2.iter(S))
    for i in range(len(col1)):
        if i < len(col2) and col1[i].next == col2[i]:
            if i > 0 and col2[i - 1].below != col2[i]:
                col2[i].above = col2[i - 1]
            continue
        empty_field = EmptyDataField()
        col1[i].next = empty_field
        if i > 0:
            col2[i - 1].below = empty_field
        col2.insert(i, empty_field)

    while True:
        if not head2.above:
            return head2
        head2 = head2.above
