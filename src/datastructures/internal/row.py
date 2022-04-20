from datastructures.internal.field import Field


class Row:
    fields: list[Field]
    dropped: bool

    def __init__(self):
        self.fields = []
        self.dropped = False

    @property
    def x0(self):
        return self.fields[0].x0

    @property
    def x1(self):
        return self.fields[-1].x1

    @property
    def y0(self):
        # TODO: Check why default is needed.
        return min([field.y0 for field in self.fields], default=0)

    @property
    def y1(self):
        # TODO: Check why default is needed.
        return max([field.y1 for field in self.fields], default=0)

    @property
    def text(self):
        return " ".join([field.text for field in self.fields])

    @property
    def values(self):
        return self.x0, self.x1, self.y0, self.y1, self.fields

    def add(self, new_field: Field):
        """ Adds new_field to the list of fields, preserving order. """
        i = 0
        for field in self.fields:
            if new_field.x0 < field.x0:
                break
            i += 1
        self.fields.insert(i, new_field)

    def from_list(self, fields: list[Field]):
        for field in fields:
            self.add(field)
        return self

    def get_columns(self):
        return [(field.x0, field.x1) for field in self.fields]

    def __repr__(self):
        return (f"Row(x0={self.x0}, x1={self.x1}, "
                f"y0={self.y0}, y1={self.y1}, "
                f"count={len(self.fields)}, text='{self.text}')")
