""" Subpackage containing all necessary functions/classes,
to create a valid gtfs zip file. """

from __future__ import annotations

import logging
from dataclasses import dataclass, Field, fields
from pathlib import Path
from typing import Iterator, Optional, Type, TypeVar

import pandas as pd

from utils import next_uid, UIDGenerator


logger = logging.getLogger(__name__)


@dataclass
class BaseDataClass:
    """ Base class for a single entry in a gtfs file. """

    def __init__(self, existing_id: str | None = None) -> None:
        self.id: str = next_uid() if existing_id is None else existing_id

    @classmethod
    def get_field_names(cls: BaseDataClass) -> str:
        """ Returns the field_names (headers) of the entry. """
        # STYLE: move to BaseContainer, bc a file has headers not an entry?
        return ",".join([field.name for field in fields(cls)])

    def get_field_value(self, field: Field):
        """ Returns the value of the given field. """
        return getattr(self, field.name)

    def _to_output(self, field: Field) -> str:
        value = self.get_field_value(field)
        if hasattr(value, "to_output") and callable(value.to_output):
            return value.to_output()
        if isinstance(value, str):
            return str_wrap(value)
        return str(value)

    def to_output(self) -> str:
        """ Returns this object, as it would be found within a GTFS file. """
        return ",".join(map(self._to_output, fields(self)))


DCType = TypeVar("DCType", bound=BaseDataClass)


class BaseContainer:
    """ Base class for a GTFS file. """

    entries: list[DCType]

    def __init__(self, filename: str, entry_type: Type[DCType], path: Path):
        self.fp = path.joinpath(filename)
        self.entry_type = entry_type
        self.entries: list[DCType] = []

    def _add(self, entry: DCType) -> DCType:
        if entry in self.entries:
            return self.entries[self.entries.index(entry)]
        self.entries.append(entry)
        return entry

    def _get(self, new_entry: DCType) -> Optional[DCType]:
        """ Returns the first entry equal to the argument, in case it exists,
        otherwise None. If the entry type cannot be compared, return the
        argument instead. """
        if not hasattr(self.entry_type, "__eq__"):
            return new_entry
        for entry in self.entries:
            if entry == new_entry:
                return entry
        return None

    def to_output(self) -> str:
        """ Return the content of the gtfs file. """
        field_names = self.entry_type.get_field_names()
        entry_output = "\n".join(
            map(lambda entry: entry.to_output(), self.entries))
        return f"{field_names}\n{entry_output}\n"

    def write(self) -> None:
        """ Write the file content to the output directory. """
        self._write(self.to_output())

    def _write(self, content: str) -> None:
        with open(self.fp, "w") as fil:
            fil.write(content)

    def __iter__(self) -> Iterator[DCType]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.entries!r}"


class ExistingBaseContainer(BaseContainer):
    """ Base class for gtfs files, which may be existing. """

    def __init__(self, filename: str, entry_type: Type[DCType], path: Path):
        super().__init__(filename, entry_type, path)
        self.overwrite = False
        self.initialize()

    def initialize(self) -> None:
        """ Add all existing entries. """
        self.entries = self.from_file()
        for entry in self.entries:
            UIDGenerator.skip(entry.id)

    def from_file(self, default=None) -> list[DCType]:
        """ Read the existing file, returning a list of all entries.
         If the file does not exist, return the default instead. """

        if default is None:
            default = []
        if not self.fp.exists():
            return default
        logger.info(f"Reading existing file {self.fp}...")
        try:
            df = pd.read_csv(self.fp, dtype=str)
        except Exception as e:
            def_msg = (f"Found existing file {self.fp}, but when trying to "
                       f"read it, the following exception occurred:\n{e}")
            logger.warning(def_msg)
            self.overwrite = True
            return default
        entries = self.entries_from_df(df)
        if not entries:
            self.overwrite = True
            return default
        return entries

    def entries_from_df(self, df: pd.DataFrame) -> list[DCType]:
        """ Turn the given dataframe into entries with the correct type. """
        entries = []
        for _, values in df.iterrows():
            entries.append(self.entry_type.from_series(values))
        return entries


def str_wrap(value) -> str:
    """ Wrap a value in apostrophes. """
    return f"\"{str(value)}\""
