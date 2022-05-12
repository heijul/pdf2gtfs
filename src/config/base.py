from pathlib import Path
from typing import Any

from yaml import safe_load, YAMLError
from yaml.scanner import ScannerError

from config.errors import (
    InvalidPropertyTypeError, MissingRequiredPropertyError)
from config.properties import Property, PagesProperty, FilenameProperty


class InstanceDescriptorMixin:
    """ Enable descriptors on an instance instead of a class.
    See https://blog.brianbeck.com/post/74086029/instance-descriptors
    """

    def __getattribute__(self, name):
        value = object.__getattribute__(self, name)
        if hasattr(value, '__get__'):
            value = value.__get__(self, self.__class__)
        return value

    def __setattr__(self, name, value):
        try:
            obj = object.__getattribute__(self, name)
        except AttributeError:
            pass
        else:
            if hasattr(obj, '__set__'):
                return obj.__set__(self, value)
        return object.__setattr__(self, name, value)


class _Config(InstanceDescriptorMixin):
    INVALID_CONFIG_EXIT_CODE = 1

    def __init__(self):
        self._initialize_config_properties()
        # Always load default config first, before loading any custom config
        # or program parameters.
        default_config_loaded = self.load_config(None)
        if not default_config_loaded:
            print(f"ERROR: Default config could not be loaded. Exiting...")
            quit(_Config.INVALID_CONFIG_EXIT_CODE)

    def _initialize_config_properties(self):
        self.properties = []
        self.time_format = Property(self, "time_format", str)
        self.header_identifier = Property(self, "header_identifier", list)
        self.repeat_identifier = Property(self, "repeat_identifier", list)
        self.min_table_rows = Property(self, "min_table_rows", int)
        self.pages = PagesProperty(self, "pages", list)
        self.max_row_distance = Property(self, "max_row_distance", int)
        self.filename = FilenameProperty(self, "filename", str)

    def load_config(self, path: Path | None = None) -> bool:
        """ Load the given config. If no config is given, load the default one.

        :param path: Path to config file, or None to load the default config.
        :return: True, if loading was a success, False if any errors occurred.
        """
        if not path:
            path = self.default_config_path
        if not path.exists():
            print(f"WARNING: File does not exist, skipping: {path}")
            return False

        data, valid = _read_yaml(path)

        for key, value in data.items():
            # Even if an item is invalid, continue reading to find all errors.
            try:
                if key not in self.properties:
                    print(f"ERROR: Invalid config key: {key}")
                    raise InvalidPropertyTypeError
                setattr(self, key, value)
            except InvalidPropertyTypeError:
                valid = False

        valid &= self._validate_no_missing_properties()

        if not valid:
            print("ERROR: Tried to load invalid configuration file. Exiting.")
            quit(_Config.INVALID_CONFIG_EXIT_CODE)

        return True

    def load_args(self, args: dict[str, Any]):
        for path in args.pop("config", []):
            self.load_config(Path(path).resolve())

        for name, value in args.items():
            if value is None:
                continue
            if name in self.properties:
                setattr(self, name, value)

    def _validate_no_missing_properties(self):
        missing_keys = []
        for key in self.properties:
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

        property_names = self.properties + ["base_path"]
        max_name_len = max(len(name) for name in property_names)
        # TODO: Add apostrophes around strings
        # TODO: Check if this fails, if a property is not set (MissingProperty)
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
