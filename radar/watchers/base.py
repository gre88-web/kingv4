from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Signal
from ..store import Store


class Watcher(ABC):
    """A source that is polled on an interval and returns new signals.

    Every watcher must treat its very first poll as a *baseline*: record the current
    state and emit nothing, so that starting the radar does not flood alerts with
    everything that already exists.
    """

    kind: str = ""

    def __init__(self, name: str, interval: float) -> None:
        self.name = name
        self.interval = interval

    @abstractmethod
    def poll(self, store: Store) -> list[Signal]:
        ...

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name}>"
