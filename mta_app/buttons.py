from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from gpiozero import Button


@dataclass
class ButtonEvent:
    kind: str  # LEFT | RIGHT | UP | DOWN | SELECT
    t: float


class Buttons:
    """
    5-button input with debounce.
    GPIO numbers are BCM.
    Wiring: each button between GPIO and GND (uses internal pull-ups).
    """
    def __init__(
        self,
        left_gpio: int = 16,
        right_gpio: int = 20,
        select_gpio: int = 21,
        up_gpio: int = 19,
        down_gpio: int = 26,
        debounce_s: float = 0.12,
    ):
        self.left = Button(left_gpio, pull_up=True, bounce_time=debounce_s)
        self.right = Button(right_gpio, pull_up=True, bounce_time=debounce_s)
        self.select = Button(select_gpio, pull_up=True, bounce_time=debounce_s)
        self.up = Button(up_gpio, pull_up=True, bounce_time=debounce_s)
        self.down = Button(down_gpio, pull_up=True, bounce_time=debounce_s)

        self._last_event: Optional[ButtonEvent] = None

        self.left.when_pressed = lambda: self._set("LEFT")
        self.right.when_pressed = lambda: self._set("RIGHT")
        self.select.when_pressed = lambda: self._set("SELECT")
        self.up.when_pressed = lambda: self._set("UP")
        self.down.when_pressed = lambda: self._set("DOWN")

    def _set(self, kind: str) -> None:
        self._last_event = ButtonEvent(kind=kind, t=time.time())

    def pop_event(self) -> Optional[ButtonEvent]:
        ev = self._last_event
        self._last_event = None
        return ev
