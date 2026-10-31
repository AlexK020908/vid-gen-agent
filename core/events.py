"""In-process events. Stages emit from worker threads, so listeners must be thread-safe.

Emit only after a transaction commits: listeners open their own connections and write.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger("stickfleet.events")


@dataclass
class Event:
    kind: str
    video_id: int | None
    data: dict = field(default_factory=dict)


Listener = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._listeners: list[Listener] = []
        self._lock = threading.Lock()

    def subscribe(self, fn: Listener) -> None:
        with self._lock:
            self._listeners.append(fn)

    def unsubscribe(self, fn: Listener) -> None:
        with self._lock:
            if fn in self._listeners:
                self._listeners.remove(fn)

    def emit(self, kind: str, video_id: int | None = None, /, **data) -> None:
        event = Event(kind, video_id, data)
        with self._lock:
            listeners = list(self._listeners)
        for fn in listeners:
            try:
                fn(event)
            except Exception:
                log.exception("listener failed on %s", kind)
