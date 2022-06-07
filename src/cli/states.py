from __future__ import annotations

import logging
from datetime import datetime as dt
from typing import Callable


logger = logging.getLogger(__name__)


class State:
    def __init__(self, state_machine, name: str, next_name: str = ""):
        self.sm = state_machine
        self.name = name
        self.done = False
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
            self._next = self.sm.get_state(next_state)
        self._next = next_state

    def enter(self, last_state: State):
        pass

    def exit(self):
        pass

    def run(self):
        pass


class StartState(State):
    def __init__(self, state_machine):
        super().__init__(state_machine, "start")


class EndState(State):
    def __init__(self, state_machine):
        super().__init__(state_machine, "end")


class ConditionState:
    next_states: tuple[State, State]
    condition_func: Callable[[], bool] = bool

    def __init__(self, good_state: State, bad_state: State):
        self.next_states = (good_state, bad_state)
        self.condition_func = bool

    @property
    def next(self):
        return self.next_states[int(self.check_condition())]

    def check_condition(self) -> bool:
        return self.condition_func()


class InputState(State):
    def __init__(self, state_machine, name: str, message: str):
        self.message = message
        super().__init__(state_machine, name)

    def get_input(self) -> str:
        return input(self.message).strip().lower()


class AnnotBaseState(InputState):
    def __init__(self, state_machine):
        msg = ("Found this annotation '{}'. What do you want to do?\n"
               "(S)kip annotation, Add (E)xception for this annotation, "
               "Skip (A)ll remaining annotations: [s/e/a]\n>")
        super().__init__(state_machine, "base", msg)


class AnnotAddDateState(InputState):
    def __init__(self, state_machine):
        self.dates: dt.date = []
        msg = ("Enter a date (YYYYMMDD) where service is different than usual"
               ", or an empty string if there are no more exceptions"
               "for this annotation:\n>")
        super().__init__(state_machine, "add_date", msg)

    def run(self) -> bool:
        response = self.get_input()
        if response == "":
            return True
        try:
            date = dt.strptime(response, "%Y%m%d")
        except ValueError:
            logger.warning("Invalid date. Make sure you use the "
                           "right format (e.g. 20220420).")
            return False

        self.dates.append(date)
        return True


class AnnotSetActiveState(InputState):
    def __init__(self, state_machine):
        msg = ("Do you want service to be (a)ctive or (d)isabled for the "
               "current annotation on the given date? [a,d]")
        self.values: list[bool] = []
        super().__init__(state_machine, "set_active", msg)

    def run(self):
        def response_to_int(_response):
            return int(_response == "d") + 1

        response = self.get_input()

        if response not in ["a", "d"]:
            logger.warning("Invalid response.")
            return False
        self.values.append(response_to_int(response))
        return True

