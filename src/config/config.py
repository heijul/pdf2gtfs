from pathlib import Path
from typing import Any

from yaml import safe_load, YAMLError
from yaml.scanner import ScannerError


INVALID_CONFIG_EXIT_CODE = 1


class ConfigProperty:
    def __init__(self, attr):
        self.attr = "__" + attr

    def __get__(self, obj, objtype=None):
        return getattr(obj, self.attr)

    def __set__(self, obj, value):
        setattr(obj, self.attr, value)


class _Config:
    properties = {"time_format": str,
                  "header_identifier": list,
                  "repeat_identifier": list,
                  }

    time_format = ConfigProperty("time_format")
    header_identifier = ConfigProperty("header_identifier")
    repeat_identifier = ConfigProperty("repeat_identifier")

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
            if not _validate_config_item(key, value):
                valid = False
                continue
            setattr(self, key, value)

        valid &= self._validate_no_missing_properties()

        if not valid:
            print("ERROR: Tried loading invalid configuration file. Exiting.")
            quit(INVALID_CONFIG_EXIT_CODE)

    def load_args(self, args: list[tuple[str, Any]]):
        for name, value in args:
            if value is None:
                continue
            if name in _Config.properties:
                setattr(self, name, value)

    def _validate_no_missing_properties(self):
        missing_keys = [key for key in _Config.properties.keys()
                        if not hasattr(self, key)]

        if missing_keys:
            print("The following keys are required, but are missing in "
                  "the configuration: {}. ".format("\n".join(missing_keys)) +
                  "This usually only happens, if the default configuration "
                  "was changed, instead of creating a custom one.")
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

        property_names = list(_Config.properties.keys()) + ["base_path"]
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


def _validate_config_item(key: str, value: Any) -> bool:
    def _validate_config_key() -> bool:
        if key not in _Config.properties:
            print(f"ERROR: Invalid config key: {key}")
            return False
        return True

    def _validate_config_type() -> bool:
        typ = _Config.properties.get(key)
        if not isinstance(value, typ):
            print(f"ERROR: Invalid config type for {key}. "
                  f"Expected '{typ}', got '{type(value)}' instead.")
            return False
        return True

    return _validate_config_key() and _validate_config_type()


Config = _Config()
