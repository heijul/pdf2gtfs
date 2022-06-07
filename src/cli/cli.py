from __future__ import annotations
from typing import TYPE_CHECKING, TypeVar
from datetime import datetime as dt

from cli.states import (State, StartState, EndState, AnnotBaseState,
                        AnnotAddDateState, AnnotSetActiveState)


if TYPE_CHECKING:
    from datastructures.gtfs_output.handler import GTFSHandler

S_Type = TypeVar("S_Type", bound="State")


class InputHandler:
    states: dict[str, S_Type]
    current: S_Type

    def __init__(self):
        self.states = {"start": StartState(self),
                       "end": EndState(self)}
        self.current = self.states["start"]

    @property
    def done(self) -> bool:
        return isinstance(self.current, EndState)

    def get_state(self, name: str) -> State:
        return self.states[name]

    def _next_state(self):
        last = self.current
        self.current.exit()
        self.current = self.current.next
        if self.current is not None:
            self.current.enter(last)

    def run(self):
        while True:
            if self.current.run():
                self._next_state()
            if self.done:
                break


class AnnotationInputHandler(InputHandler):
    def __init__(self, gtfs_handler: GTFSHandler, annotations_: set[str]):
        self.handler = gtfs_handler
        self.annotations = annotations_
        super().__init__()
        self.create_states()

    def create_states(self):
        states = [AnnotBaseState(self),
                  AnnotAddDateState(self),
                  AnnotSetActiveState(self)]
        self.states.update({state.name: state for state in states})
        self.current.next = "base"

    def get_next_annotation(self) -> str | None:
        return self.annotations.pop() if self.annotations else None

    def get_values(self) -> dict[str, dict[dt.date, bool]]:
        base_state: AnnotBaseState = self.states["base"]
        return base_state.get_value()
