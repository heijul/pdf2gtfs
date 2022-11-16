""" Subpackage containing all necessary functions/classes,
to create a valid gtfs zip file. """

from __future__ import annotations

import logging
from dataclasses import dataclass, Field, fields
from operator import methodcaller
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

    def __init__(self, file_name: str, entry_type: Type[DCType], path: Path):
        self.fp = path.joinpath(file_name)
        self.entry_type = entry_type
        self.entries: list[entry_type] = self.read_input_files()
        for entry in self.entries:
            UIDGenerator.skip(entry.id)

    def read_input_file(self, path: Path) -> list[DCType]:
        """ Try to read the given input file. """
        try:
            df = pd.read_csv(path, dtype=str)
        except Exception as e:
            logger.warning(f"The following exception occurred, when trying "
                           f"to read the input file '{path}':\n{e}")
            return []
        # FEATURE: Check, if the IDs are still unique.
        entries = self.entries_from_df(df)
        return entries

    def read_input_files(self) -> list[DCType]:
        """ Read the existing file, returning a list of all entries.
         If the file does not exist, return the default instead. """
        from config import Config

        entries = []
        for file in Config.input_files.get(self.fp.name, []):
            logger.info(f"Reading input file {file}...")
            entries += self.read_input_file(file)
        return entries

    def entries_from_df(self, df: pd.DataFrame) -> list[DCType]:
        """ Turn the given dataframe into entries with the correct type. """
        entries = []
        for _, values in df.iterrows():
            entries.append(self.entry_type.from_series(values))
        return entries

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

    def get_header(self) -> str:
        """ Returns the field_names (headers) of the entry. """
        return ",".join([field.name for field in fields(self.entry_type)])

    def to_output(self) -> str:
        """ Return the content of the gtfs file. """
        entry_output = "\n".join(map(methodcaller("to_output"), self.entries))
        return f"{self.get_header()}\n{entry_output}\n"

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


def str_wrap(value) -> str:
    """ Wrap a value in apostrophes. """
    return f"\"{str(value)}\""
