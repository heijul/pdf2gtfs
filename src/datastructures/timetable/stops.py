from utils import normalize_name


class Stop:
    def __init__(self, name: str, raw_row_id: int):
        self.name = normalize_name(name)
        self.raw_row_id = raw_row_id
        self.annotation = ""
        self.is_connection = False

    def clean(self):
        self.name = self.name.strip()

    def __eq__(self, other):
        return self.name == other.name and self.annotation == other.annotation

    def __hash__(self):
        return hash(self.name + " " + self.annotation)

    def __str__(self):
        # Add a/d for arrival/departure, depending on annotation.
        annots = {"an": " [a]", "ab": " [d]"}
        return self.name.strip() + annots.get(self.annotation.strip(), "")

    def __repr__(self):
        return f"'{str(self)}'"


class DummyAnnotationStop(Stop):
    # Used only in the timetable.table.Table.__str__ method
    def __init__(self):
        super(DummyAnnotationStop, self).__init__("", 0)

    def __str__(self) -> str:
        return "ANNOTATIONS"
