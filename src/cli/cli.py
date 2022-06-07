from __future__ import annotations
from typing import TYPE_CHECKING

from cli.states import (State, StartState, EndState, AnnotBaseState,
                        AnnotAddDateState, AnnotSetActiveState)


if TYPE_CHECKING:
    from datastructures.gtfs_output.handler import GTFSHandler


class InputHandler:
    states: dict[str, State]
    current: State

    def __init__(self):
        self.states = {"start": StartState(self),
                       "end": EndState(self)}
        self.current = self.states["start"]

    @property
    def done(self) -> bool:
        return isinstance(self.current, EndState)

    def _next_state(self):
        last = self.current
        self.current.exit()
        self.current = self.current.next
        if self.current is not None:
            self.current.enter(last)

    def run(self):
        while True:
            self.current.run()
            self._next_state()
            if self.done:
                break


class AnnotationInputHandler(InputHandler):
    def __init__(self, gtfs_handler: GTFSHandler, annotations_: set[str]):
        super().__init__()
        self.create_states()
        self.handler = gtfs_handler
        self.annotations = annotations_

    def create_states(self):
        states = [AnnotBaseState(self),
                  AnnotAddDateState(self),
                  AnnotSetActiveState(self)]
        self.states.update({state.name: state for state in states})
