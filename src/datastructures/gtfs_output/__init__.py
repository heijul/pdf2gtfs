from __future__ import annotations

from dataclasses import dataclass, fields, Field
from pathlib import Path
from typing import TypeVar, Type

from utils import next_uid


@dataclass
class BaseDataClass:
    def __init__(self):
        self.id = next_uid()

    @classmethod
    def get_field_names(cls: BaseDataClass) -> str:
        return ",".join([field.name for field in fields(cls)])

    def get_field_value(self, field: Field):
        return getattr(self, field.name)

    def _to_output(self, field: Field):
        value = self.get_field_value(field)
        if hasattr(value, "to_output") and callable(value.to_output):
            return value.to_output()
        return str(value)

    def to_output(self) -> str:
        # TODO: Add escape for strings
        return ",".join(map(self._to_output, fields(self)))


ContainerObjectType = TypeVar("ContainerObjectType", bound=BaseDataClass)


class BaseContainer:
    entries: list[ContainerObjectType]

    def __init__(self, filename: str, entry_type: Type[ContainerObjectType]):
        self.filename = filename
        self.entry_type = entry_type
        self.entries: list[ContainerObjectType] = []

    def _add(self, entry: ContainerObjectType) -> None:
        self.entries.append(entry)

    def to_output(self):
        field_names = self.entry_type.get_field_names()
        entry_output = "\n".join(
            map(lambda entry: entry.to_output(), self.entries))
        return f"{field_names}\n{entry_output}\n"

    def write(self, path: Path):
        self._write(path, self.to_output() + "\n")

    def _write(self, path: Path, content: str) -> None:
        # TODO: Probably need to ensure path ends with a seperator.
        # TODO: @cli also needs to ask if files should be overridden.
        with open(path.joinpath(self.filename), "w") as fil:
            fil.write(content)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.entries!r}"
