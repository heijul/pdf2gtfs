from __future__ import annotations

import logging
from dataclasses import dataclass, fields, Field
from pathlib import Path
from typing import TypeVar, Type

import pandas as pd

from user_input.cli import overwrite_existing_file
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

    @property
    def fp(self):
        from config import Config
        return Path(Config.output_dir).resolve().joinpath(self.filename)

    def _add(self, entry: ContainerObjectType) -> None:
        self.entries.append(entry)

    def to_output(self):
        field_names = self.entry_type.get_field_names()
        entry_output = "\n".join(
            map(lambda entry: entry.to_output(), self.entries))
        return f"{field_names}\n{entry_output}\n"

    def write(self):
        self._write(self.to_output() + "\n")

    def _write(self, content: str) -> None:
        from config import Config

        if self.fp.exists():
            if not Config.always_overwrite and Config.non_interactive:
                logger.warning(
                    f"File {self.fp} already exists and overwriting "
                    f"is disabled.")
                return
            if not Config.always_overwrite and not Config.non_interactive:
                if not overwrite_existing_file(self.fp):
                    return

        with open(self.fp, "w") as fil:
            fil.write(content)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.entries!r}"


class ExistingBaseContainer(BaseContainer):
    def __init__(self, filename: str, entry_type: Type[ContainerObjectType]):
        super().__init__(filename, entry_type)

    def write(self) -> None:
        """ Never overwrite existing files. """
        if self.fp.exists():
            return
        super().write()

    def from_file(self, default=None) -> list[ContainerObjectType]:
        if default is None:
            default = []
        if not self.fp.exists():
            return default
        # TODO: Add error catching + msg
        entries = self.entries_from_df(pd.read_csv(self.fp, dtype=str))
        if not entries:
            return default
        return entries

    def entries_from_df(self, df: pd.DataFrame) -> list[ContainerObjectType]:
        entries = []
        for _, values in df.iterrows():
            entries.append(self.entry_type.from_series(values))
        return entries
