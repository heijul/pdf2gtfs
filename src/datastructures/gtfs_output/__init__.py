""" Subpackage containing all necessary functions/classes,
to create a valid gtfs zip file. """


from __future__ import annotations

import logging
from dataclasses import dataclass, Field, fields
from pathlib import Path
from typing import Iterator, Optional, Type, TypeVar

import pandas as pd

from user_input.cli import overwrite_existing_file
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
        """ Returns a formatted line, as it would be found within a gtfs file. """
        return ",".join(map(self._to_output, fields(self)))


DCType = TypeVar("DCType", bound=BaseDataClass)


class BaseContainer:
    """ Base class for a gtfs file. """

    entries: list[DCType]

    def __init__(self, filename: str, entry_type: Type[DCType]):
        self.filename = filename
        self.entry_type = entry_type
        self.entries: list[DCType] = []

    @property
    def fp(self) -> Path:
        """ Return the absolute filepath of the file. """
        from config import Config
        # STYLE: Remove filename if not used elsewhere and override.
        return Path(Config.output_dir).joinpath(self.filename).resolve()

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

    def __iter__(self) -> Iterator[DCType]:
        return iter(self.entries)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.entries!r}"


class ExistingBaseContainer(BaseContainer):
    """ Base class for gtfs files, which may be existing. """
    def __init__(self, filename: str, entry_type: Type[DCType]):
        super().__init__(filename, entry_type)
        self.overwrite = False
        self.initialize()

    def initialize(self) -> None:
        """ Add all existing entries. """
        for entry in self.from_file():
            self._add(entry)
            UIDGenerator.skip(entry.id)

    def write(self) -> None:
        """ Write the file content to the output directory, without
        overwriting existing files, unless it is forced (see self.overwrite). """
        if self.fp.exists() and not self.overwrite:
            return
        super().write()

    def from_file(self, default=None) -> list[DCType]:
        """ Read the existing file, returning a list of all entries.
         If the file does not exist, return the default instead. """

        if default is None:
            default = []
        if not self.fp.exists():
            return default
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
