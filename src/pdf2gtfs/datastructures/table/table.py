from __future__ import annotations

from itertools import pairwise
from operator import attrgetter
from typing import Callable, Iterable, TypeVar

from more_itertools import (
    always_iterable, first_true, flatten, peekable, split_when, spy,
    take, triplewise,
    )

from pdf2gtfs.config import Config
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


def merge_overlapping_fields(o: Orientation, fields: Fs) -> None:
    if o == V:
        groups = fields_to_rows(fields, link_rows=False)
    else:
        groups = fields_to_cols(fields, link_cols=False)
    for group in groups:
        field = group[0]
        for field2 in group[1:]:
            field.merge(field2)


def merge_small_fields(o: Orientation, ref_fields: Fs, fields: Fs
                       ) -> None:
    if len(fields) < 2:
        return
    n = o.normal
    overlaps = {}
    first_ref_id = 0
    for field in fields:
        field_overlaps = []
        for i, ref_field in enumerate(ref_fields[first_ref_id:], first_ref_id):
            if ref_field.is_overlap(n, field, 0.8):
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
            e.bbox = BBox(ref_field.bbox.x0, field.bbox.y0,
                          ref_field.bbox.x1, field.bbox.y1)
        else:
            e.bbox = BBox(field.bbox.x0, ref_field.bbox.y0,
                          field.bbox.x1, ref_field.bbox.y1)

        field.set_neighbor(o.lower, e)

    # Add empty nodes at the end.
    field = fields[-1]
    while field_count < len(ref_fields):
        e = EmptyField()
        ref_field = ref_fields[field_count]
        if o == H:
            e.bbox = BBox(ref_field.bbox.x0, field.bbox.y0,
                          ref_field.bbox.x1, field.bbox.y1)
        else:
            e.bbox = BBox(field.bbox.x0, ref_field.bbox.y0,
                          field.bbox.x1, ref_field.bbox.y1)
        field.set_neighbor(o.upper, e)
        field_count += 1
        field = e

    # Return head
    field = fields[0]
    while field.has_neighbors(d=o.lower):
        field = field.get_neighbor(o.lower)
    return field


class Table(QuadLinkedList[F, OF]):
    def __init__(self, first_node: F, last_node: F):
        super().__init__(first_node, last_node)

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

    def get_empty_field_bbox(self, node: EmptyField) -> BBox:
        row_bbox = self.get_bbox_of(self.row(node))
        col_bbox = self.get_bbox_of(self.col(node))
        return BBox(col_bbox.x0, row_bbox.y0, col_bbox.x1, row_bbox.y1)

    def expand(self, d: Direction, fields: Fs) -> bool:
        normal = d.default_orientation.normal
        ref_fields = list(self.iter(normal.upper, self.get_end_node(d)))
        adjacent_fields = select_adjacent_fields(d, ref_fields, fields)
        if not adjacent_fields:
            return False

        link_nodes(normal.upper, adjacent_fields)
        # merge_overlapping_fields(
        #  d.default_orientation.normal, adjacent_fields)
        merge_small_fields(d.default_orientation, ref_fields, adjacent_fields)

        head = insert_empty_fields_from_map(
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

    def get_contained_fields(self, fields: Fs) -> Fs:
        def _both_overlap(field: F) -> bool:
            return (bbox.is_v_overlap(field.bbox, 0.8) and
                    bbox.is_h_overlap(field.bbox, 0.8))
        bbox = BBox.from_bboxes([self.get_bbox_of(self.col(self.left)),
                                 self.get_bbox_of(self.col(self.right)),
                                 self.get_bbox_of(self.row(self.top)),
                                 self.get_bbox_of(self.row(self.bot))])
        fields = list(filter(_both_overlap, fields))
        return fields

    def find_repeat_intervals(self, fields: Fs) -> list[tuple[F, F, F]]:
        cols = fields_to_cols(fields, link_cols=False)
        repeat_intervals = []
        for col in cols:
            triple = triplewise(col)
            for f1, f2, f3 in triple:
                repeat_text = [f1.text.lower(), f3.text.lower()]
                if repeat_text not in Config.repeat_identifier:
                    continue
                if not f2.text.isnumeric():
                    continue
                repeat_intervals.append((f1, f2, f3))
                # No need to check the next two triples.
                take(2, triple)
        return repeat_intervals

    def get_containing_col(self, field: F) -> Fs:
        for col_field in self.left.iter(E):
            if col_field.is_overlap(H, field, 0.8):
                return list(self.col(col_field))

    def get_col_left_of(self, field: F) -> Fs:
        return list(self.col(
            first_true(self.left.iter(E), default=self.right,
                       pred=lambda f: f.bbox.x0 > field.bbox.x0).prev))

    def transform_repeat_fields(self, fields: Fs) -> None:
        contained_fields = self.get_contained_fields(fields)
        repeat_intervals = self.find_repeat_intervals(contained_fields)
        if not repeat_intervals:
            return
        # TODO NOW: Transform the intervals into proper RepeatFields.
        repeat_fields = list(flatten(repeat_intervals))
        for field in repeat_fields:
            fields.remove(field)

        # Group repeat fields by col and link them.
        repeat_groups = fields_to_cols(repeat_fields)
        # Insert a new column for each repeat group.
        for group in repeat_groups:
            col = self.get_containing_col(group[0])
            if col:
                unlink_nodes(S, group)
                self.insert_fields_in(V, col, group)
                continue
            col = self.get_col_left_of(group[0])
            head = insert_empty_fields_from_map(V, col, group)
            self.insert(E, col[0], head)

    def print(self, max_len=360) -> None:
        def _get_text_align(f) -> str:
            return ">" if isinstance(f, EmptyField) else "<"

        first_column = self.get_list(V, self.left)
        rows = [self.get_list(H, field) for field in first_column]
        cols = [self.get_list(V, field) for field in rows[0]]
        col_len = [max(map(len, map(attrgetter("text"), col))) for col in cols]

        delim = " | "
        lines = []
        for row in rows:
            field_texts = [f"{f.text: {_get_text_align(f)}{col_len[i]}}"
                           for i, f in enumerate(row)]
            lines += [delim.lstrip()
                      + delim.join(field_texts)[:max_len]
                      + delim.rstrip()]

        print("\n".join(lines))

    def replace_field(self, which: F, replace_with: F) -> None:
        # New node should not have any neighbors
        assert not replace_with.has_neighbors(o=V)
        assert not replace_with.has_neighbors(o=H)
        for d in [N, S, W, E]:
            neighbor = which.get_neighbor(d)
            if not neighbor:
                continue
            which.set_neighbor(d, None)
            neighbor.set_neighbor(d.opposite, replace_with)

    def insert_fields_in(self, o: Orientation, col: Fs, fields: Fs) -> None:
        last_id = 0
        for field in fields:
            for i, col_field in enumerate(col[last_id:], last_id):
                if not col_field.is_overlap(o, field, 0.8):
                    continue
                assert col_field.is_overlap(o.normal, field, 0.8)
                self.replace_field(col_field, field)
                last_id = i + 1
                break

    def split_on_contained_splitter(self, fields: Fs) -> list[Table]:
        contained_fields = self.get_contained_fields(fields)
        if not contained_fields:
            return [self]
        rows = fields_to_rows(contained_fields, link_rows=False)
        splitter = []
        row_id = 0
        col = list(self.iter(S, self.top))
        for row in rows:
            row_bbox = BBox.from_bboxes([f.bbox for f in row])
            for i, table_row_field in enumerate(col[row_id:], row_id):
                table_row_bbox = self.get_bbox_of(self.row(table_row_field))
                if table_row_bbox.is_overlap("v", row_bbox):
                    row_id = i
                    break
                if table_row_bbox.y0 > row_bbox.y0:
                    splitter.append(row)
                    row_id = i
                    break
        if not splitter:
            return [self]
        table_fields = self.split_at_row_fields(splitter)
        tables = []
        for fields in table_fields:
            head = fields[0]
            if head.qll != self:
                continue
            field = None
            # Unlink last row.
            for field in self.iter(E, fields[-1]):
                field.set_neighbor(S, None)
            tables.append(Table(head, field))
        # TODO NOW: Remove empty cols.
        return tables

    def split_at_row_fields(self, row_fields: Fs) -> list[Fs]:
        def _same_table(field1: F, field2: F) -> bool:
            return field1.qll != field2.qll

        fields = list(self.top.iter(S)) + list(flatten(row_fields))
        return group_fields_by(fields, _same_table, "bbox.y0", None)


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


def fields_to_cols(fields: Fs, *, link_cols: bool = True) -> Cols:
    """ Turns the datafields into a collection of columns. """
    def _same_col(field1: F, field2: F) -> bool:
        """ Two fields are in the same column if they overlap horizontally. """
        return not field1.bbox.is_h_overlap(field2.bbox)

    cols = group_fields_by(fields, _same_col, "bbox.x0", "bbox.y0")
    if link_cols:
        for col in cols:
            link_nodes(S, col)
    return cols


def fields_to_rows(fields: Fs, *, link_rows: bool = True) -> Rows:
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
    p = peekable(fields)
    for field in p:
        field.set_neighbor(d, p.peek(None))


def unlink_nodes(d: Direction, fields: Fs) -> None:
    for field in fields:
        field.set_neighbor(d, None)


def link_rows_and_cols(rows: list[Fs], cols: list[Fs]) -> None:
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
    insert_empty_fields_from_map(V, first_field_of_rows, first_col)
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
