from __future__ import annotations

from functools import partial
from typing import Iterator, Type, TypeAlias, TypeVar, Union

from more_itertools import partition

from pdf2gtfs.datastructures.pdftable.bbox import BBox, BBoxObject
from pdf2gtfs.datastructures.table.fields import EmptyTableField, F
from pdf2gtfs.datastructures.table.linked_list import (
    DLL, DoublyLinkedList, LLNode)


FC = TypeVar("FC", bound="FieldContainer")
TRow = TypeVar("TRow", bound="Row")
TCol = TypeVar("TCol", bound="Col")

TRowNode = TypeVar("TRowNode", LLNode["Row"], LLNode["Col"])


# When any single container is required.
C: TypeAlias = Union["Row", "Col"]


class FieldContainer(DoublyLinkedList[F], LLNode[FC], BBoxObject):
    """ Baseclass for Rows and Cols. """
    @BBoxObject.bbox.getter
    def bbox(self) -> BBox:
        """ The bounding box of the whole row/col. """
        msg = "BBox needs to be set first."
        assert self._bbox is not None and self._bbox != BBox(), msg
        return self._bbox

    def set_bbox_from_fields(self) -> None:
        """ Sets the bbox, such that all the fields are completely within. """
        bbox = None
        for field in self:
            field_bbox = field.bbox
            # This may happen for empty fields.
            if field_bbox is None:
                continue
            if not bbox:
                bbox = BBox(field.bbox.x0, field.bbox.y0,
                            field.bbox.x1, field.bbox.y1)
                continue
            if field.bbox.x0 < bbox.x0:
                bbox.x0 = field.bbox.x0
            if field.bbox.x1 > bbox.x1:
                bbox.x1 = field.bbox.x1
            if field.bbox.y0 < bbox.y0:
                bbox.y0 = field.bbox.y0
            if field.bbox.y1 > bbox.y1:
                bbox.y1 = field.bbox.y1
        # TODO NOW: ???
        super().bbox = bbox

    def set_empty_field_bboxes(self, field: EmptyTableField = None) -> None:
        """ Set the empty fields bbox based on its row and column.

        If the argument is given, only set that fields' bbox.
        Otherwise, all empty fields' bboxes in this container will be set.
        """
        if field:
            field.set_bbox_from_col_and_row()
            return
        for field in [f for f in self if isinstance(f, EmptyTableField)]:
            field.set_bbox_from_col_and_row()


class Row(FieldContainer, LLNode[TRow]):
    """ A single row in a table. """

    @classmethod
    def from_objects(cls: Type[DLL], objects: list[F]) -> DLL:
        row = super().from_objects(objects)
        for field in row:
            field.row = row
        return row


class Col(FieldContainer):
    """ A single column of a table. """
    @classmethod
    def from_objects(cls: Type[TCol], objects: list[F]) -> DLL:
        col = super().from_objects(objects)
        for field in col:
            field.col = col
        return col

    def construct_from_overlapping_fields(self, fields: Iterator[F]) -> Col:
        """ Create a new col, using the fields.

        :param fields: The list of fields, that will be added, in place of
         empty fields. This method assumes, that no new Rows need to be
         created, that is, each field in fields fits into one (existing) Row.
        """

        col = Col()
        for col_field in self:
            func = partial(col_field.bbox.is_v_overlap, relative_amount=0.66)
            fields, overlaps = partition(func, fields)
            # TODO NOW: This will only add a single field. Instead we should
            #  merge the fields / add them both as LLNode.value.
            new_field = next(overlaps) if overlaps else EmptyTableField()
            col.append(new_field)
        return col


class Rows(DoublyLinkedList[Row]):
    """ A collection of rows of a single table. """


class Cols(DoublyLinkedList[Col]):
    """ A collection of columns of a single table. """


def link_fields(dec_linker_attr: str, fields: list[F]) -> None:
    """ Link the fields using the linker_attr. The linker_attr should be one
    of prev/above. """
    prev = fields[0]
    for field in fields[1:]:
        setattr(field, dec_linker_attr, prev)
        prev = field
