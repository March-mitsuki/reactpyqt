from __future__ import annotations
from typing import Callable, Any

from .globalvar import __listener__


SignalAccessor = Callable[[], Any]
SignalSetter = Callable[[Any], None]


class Signal:
    def __init__(self, init_value):
        super().__init__()
        self._value = init_value
        self._subscribers = set()

    def __repr__(self) -> str:
        return f"<Signal value={self._value}>"

    def get(self):
        if __listener__:
            self._subscribers.add(__listener__)
        return self._value

    def set(self, next_value):
        if callable(next_value):
            self._value = next_value(self._value)
        else:
            if self._value == next_value:
                return
            self._value = next_value

        for subscriber in self._subscribers:
            subscriber()

    def subscribe(self, cb):
        self._subscribers.add(cb)


def create_effect(cb):
    global __listener__
    prev_listener = __listener__
    __listener__ = cb
    cb()
    __listener__ = prev_listener


def create_signal(value) -> tuple[SignalAccessor, SignalSetter]:
    s = Signal(value)

    return (s.get, s.set)


def create_memo(cb):
    value, set_value = create_signal(None)
    create_effect(lambda: set_value(cb()))
    return value


def untrack(cb):
    global __listener__
    prev_listener = __listener__
    __listener__ = None
    try:
        return cb()
    finally:
        __listener__ = prev_listener


def on_mount(cb):
    create_effect(lambda: untrack(cb))


def with_text(template: str, *args: SignalAccessor) -> SignalAccessor:
    result, set_result = create_signal("")
    create_effect(lambda: set_result(template.format(*[arg() for arg in args])))
    return result


def map_list(list: SignalAccessor, map_cb: Callable[[Any, int], None]) -> Callable:
    result, set_result = create_signal([])
    create_effect(
        lambda: set_result([map_cb(item, idx) for idx, item in enumerate(list())])
    )
    return result
