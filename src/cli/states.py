from __future__ import annotations

import logging
from datetime import datetime as dt
from typing import TYPE_CHECKING, TypeVar


if TYPE_CHECKING:
    from cli.cli import AnnotationInputHandler, OverwriteInputHandler


logger = logging.getLogger(__name__)
SM_Type = TypeVar("SM_Type", bound="InputHandler")


class State:
    def __init__(self, state_machine: SM_Type,
                 name: str, next_name: str = ""):
        self.sm = state_machine
        self.name = name
        self._next = None
        self.next_name = next_name

    @property
    def next(self) -> State:
        if self._next is None and self.next_name:
            self.next = self.next_name
        return self._next

    @next.setter
    def next(self, next_state: str | State) -> None:
        if isinstance(next_state, str):
            next_state = self.sm.get_state(next_state)
        self._next = next_state

    def enter(self, last_state: State):
        pass

    def exit(self):
        pass

    def run(self) -> bool:
        return True


class StartState(State):
    def __init__(self, state_machine):
        super().__init__(state_machine, "start")


class EndState(State):
    def __init__(self, state_machine):
        super().__init__(state_machine, "end")


class InputState(State):
    def __init__(self, state_machine, name: str, message: str,
                 next_name: str = ""):
        self.message = message
        super().__init__(state_machine, name, next_name)

    @staticmethod
    def get_input(message) -> str:
        return input(message + "\n> ").strip().lower()


class AnnotBaseState(InputState):
    def __init__(self, state_machine: AnnotationInputHandler):
        msg = ("Found this annotation '{}'. What do you want to do?\n"
               "(S)kip annotation, Add (E)xception for this annotation, "
               "Skip (A)ll remaining annotations: [s/e/a]")
        self.values: dict[str, list[tuple[dt.date, bool]]] = {}
        super().__init__(state_machine, "base", msg, "add_date")
        self.sm: AnnotationInputHandler
        self._update_annot()

    def enter(self, last_state: State):
        if isinstance(last_state, AnnotAddDateState):
            self._update_annot()

    def _update_annot(self):
        self.annot: str = self.sm.get_next_annotation()

    def run(self) -> bool:
        if not self.annot:
            self.next = "end"
            return True

        response = self.get_input(self.message.format(self.annot))

        if response == "s":
            self._update_annot()
            if self.annot:
                return False
            self.next = "end"
            return True
        if response == "e":
            self.next = "add_date"
            return True
        if response == "a":
            self.next = "end"
            return True
        return False

    def get_value(self):
        return self.values

    def add_value(self, value: tuple[dt.date, bool]):
        self.values[self.annot] = (
            self.values.setdefault(self.annot, []) + [value])


# TODO: Add AnnotSetDefaultState() where user can set whether this service
#  should be usually active or not.


class AnnotAddDateState(InputState):
    def __init__(self, state_machine):
        msg = ("Enter a date (YYYYMMDD) where service is different than usual"
               ", or an empty string if there are no more exceptions "
               "for this annotation:")
        self.date = None
        self.base: AnnotBaseState | None = None
        super().__init__(state_machine, "add_date", msg, "set_active")

    def enter(self, last_state: State):
        if isinstance(last_state, AnnotBaseState):
            self.base = last_state
        if isinstance(last_state, AnnotSetActiveState):
            self.base.add_value((self.date, last_state.get_value()))

    def run(self) -> bool:
        response = self.get_input(self.message)
        if response == "":
            self.next = "base"
            return True
        try:
            self.date = dt.strptime(response, "%Y%m%d")
        except ValueError:
            logger.error("Invalid date. Make sure you use the "
                         "right format (i.e. YYYYMMDD, e.g. 20220420).")
            self.date = None
            return False
        return True


class AnnotSetActiveState(InputState):
    def __init__(self, state_machine):
        msg = ("Do you want service to be (a)ctive or (d)isabled for the "
               "current annotation on the given date? [a,d]")
        self.value: bool = False
        super().__init__(state_machine, "set_active", msg, "add_date")

    def get_value(self) -> bool:
        return self.value

    def run(self):
        response = self.get_input(self.message)

        if response not in ["a", "d"]:
            logger.error("Invalid response.")
            return False

        self.value = response == "a"
        return True


class OverwriteBaseState(InputState):
    def __init__(self, state_machine: OverwriteInputHandler):
        msg = ("The file {} already exists.\nDo you want to overwrite it? "
               "[y]es [n]o")
        # FEATURE: Extend to overwrite all/none/overwrite/skip
        self.overwrite = False
        super().__init__(state_machine, "base", msg, "end")
        self.sm: OverwriteInputHandler

    def run(self):
        response = self.get_input(self.message.format(self.sm.filename))

        if response not in ["y", "n"]:
            logger.error("Invalid response.")
            return False

        self.overwrite = response == "y"
        return True
