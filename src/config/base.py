from pathlib import Path
from typing import Any

from yaml import safe_load, YAMLError
from yaml.scanner import ScannerError

from config.errors import (
    InvalidPropertyTypeError, MissingRequiredPropertyError)
from config.properties import Property, PagesProperty


class _Config:
    INVALID_CONFIG_EXIT_CODE = 1

    properties = ["time_format",
                  "header_identifier",
                  "repeat_identifier",
                  "min_table_rows",
                  "pages",
                  "max_row_distance",
                  ]

    time_format = Property("time_format", str)
    header_identifier = Property("header_identifier", list)
    repeat_identifier = Property("repeat_identifier", list)
    min_table_rows = Property("min_table_rows", int)
    pages = PagesProperty("pages")
    max_row_distance = Property("max_row_distance", int)

    def __init__(self):
        # Always load default config first, to allow users to overwrite
        # only specific properties.
        self.load_config(None)

    def load_config(self, path: Path | None = None):
        if not path:
            path = self.default_config_path

        data, valid = _read_yaml(path)

        for key, value in data.items():
            # Even if an item is invalid, continue reading to find all errors.
            try:
                if key not in _Config.properties:
                    print(f"ERROR: Invalid config key: {key}")
                    raise InvalidPropertyTypeError
                setattr(self, key, value)
            except InvalidPropertyTypeError:
                valid = False

        valid &= self._validate_no_missing_properties()

        if not valid:
            print("ERROR: Tried loading invalid configuration file. Exiting.")
            quit(_Config.INVALID_CONFIG_EXIT_CODE)

    def load_args(self, args: list[tuple[str, Any]]):
        for name, value in args:
            if value is None:
                continue
            if name in _Config.properties:
                setattr(self, name, value)

    def _validate_no_missing_properties(self):
        missing_keys = []
        for key in _Config.properties:
            try:
                getattr(self, key)
            except MissingRequiredPropertyError:
                missing_keys.append(key)

        if missing_keys:
            print("The following values are required, but are missing in "
                  "the configuration: ['{}']. This usually only happens, "
                  "if the default configuration was changed, instead of "
                  "creating a custom one.".format("', '".join(missing_keys)))
            return False
        return True

    @property
    def base_path(self) -> Path:
        return Path(__file__).parents[2]

    @property
    def default_config_path(self):
        return self.base_path.joinpath("config.template.yaml")

    def __str__(self):
        base_string = "\nCurrent configuration: [\n{}\n]"

        property_names = _Config.properties + ["base_path"]
        max_name_len = max(len(name) for name in property_names)
        prop_strings = [f"\t{name:{max_name_len}}: {getattr(self, name)}"
                        for name in property_names]

        return base_string.format("\n".join(prop_strings))


def _read_yaml(path: Path) -> tuple[dict[str, Any], bool]:
    try:
        with open(path) as config_file:
            return safe_load(config_file), True
    except (ScannerError, YAMLError) as error:
        if isinstance(error, ScannerError):
            # Indent error message.
            message = "\n\t".join(str(error).split("\n"))
        else:
            message = str(error)
        print(f"ERROR: Could not read configuration:\n\t{message}")
    return {}, False


Config = _Config()

if __name__ == '__main__':
    pass
