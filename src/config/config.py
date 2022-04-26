from pathlib import Path

from yaml import safe_load


class Config:
    __properties = ["time_format", "header_identifier", "repeat_identifier"]

    def __init__(self):
        self._time_format = None
        self._repeat_identifier = None
        self._header_identifier = None
        self.load_default_config()

    def load_default_config(self):
        self.load_config(self.base_path.joinpath("config.template.yaml"))

    def load_config(self, path: Path):
        # TODO: Error handling + check if valid config
        with open(path) as config_file:
            yaml_config = safe_load(config_file)

        for key, value in yaml_config.items():
            if key not in Config.__properties:
                print(f"WARNING: Invalid config key: {key}")
                continue
            setattr(self, "_" + key, value)

    def load_params(self, params: dict):
        ...

    # TODO: Raise errors if any of the required properties is unset.
    # TODO: Need to define required/optional properties first.
    @property
    def time_format(self) -> str:
        return self._time_format

    @property
    def header_identifier(self) -> list[str]:
        return self._header_identifier

    @property
    def repeat_identifier(self) -> str:
        return self._repeat_identifier

    @property
    def base_path(self) -> Path:
        return Path(__file__).parents[2]

    def __str__(self):
        base_string = "\nCurrent configuration: [\n{}\n]"

        property_names = Config.__properties + ["base_path"]
        max_name_len = max(len(name) for name in property_names)
        prop_strings = [f"\t{name:{max_name_len}}: {getattr(self, name)}"
                        for name in property_names]

        return base_string.format("\n".join(prop_strings))


if __name__ == "__main__":
    c = Config()
    print(c)
