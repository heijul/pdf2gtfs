from utils import strip_forbidden_symbols


class Stop:
    def __init__(self, name: str, raw_row_id: int):
        self.name = strip_forbidden_symbols(name)
        self.raw_row_id = raw_row_id
        self.annotation = ""
        self.is_connection = False

    def clean(self):
        self.name = self.name.strip()

    def __eq__(self, other):
        return self.name == other.name and self.annotation == other.annotation

    def __hash__(self):
        # TODO: This may fail if it's a roundtrip.
        return hash(self.name + " " + self.annotation)

    def __str__(self):
        # Add a/d for arrival/departure, depending on annotation.
        annots = {"an": " [a]", "ab": " [d]"}
        return self.name.strip() + annots.get(self.annotation.strip(), "")
