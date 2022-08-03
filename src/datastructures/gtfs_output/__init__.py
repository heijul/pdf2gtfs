from __future__ import annotations

import logging
from dataclasses import dataclass, fields, Field
from pathlib import Path
from typing import TypeVar, Type

from cli.cli import OverwriteInputHandler
from utils import next_uid


logger = logging.getLogger(__name__)


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
        return ",".join(map(self._to_output, fields(self)))


ContainerObjectType = TypeVar("ContainerObjectType", bound=BaseDataClass)


class BaseContainer:
    entries: list[ContainerObjectType]

    def __init__(self, filename: str, entry_type: Type[ContainerObjectType]):
        self.filename = filename
        self.entry_type = entry_type
        self.entries: list[ContainerObjectType] = []

    def get_filepath(self, path):
        return path.joinpath(self.filename)

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
        from config import Config

        fp = self.get_filepath(path)
        if fp.exists():
            if not Config.always_overwrite and Config.non_interactive:
                logger.warning(
                    f"File {fp} already exists and overwriting is disabled.")
                return
            if not Config.always_overwrite and not Config.non_interactive:
                handler = OverwriteInputHandler(fp)
                handler.run()
                if not handler.overwrite:
                    return

        with open(fp, "w") as fil:
            fil.write(content)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.entries!r}"
