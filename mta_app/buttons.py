# mta_app/buttons.py
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional

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
        debug: bool = True,
    ):
        self.debug = debug
        self._queue: List[ButtonEvent] = []

        # pull_up=True => idle HIGH, pressed connects to GND (LOW)
        self.left = Button(left_gpio, pull_up=True, bounce_time=debounce_s)
        self.right = Button(right_gpio, pull_up=True, bounce_time=debounce_s)
        self.select = Button(select_gpio, pull_up=True, bounce_time=debounce_s)
        self.up = Button(up_gpio, pull_up=True, bounce_time=debounce_s)
        self.down = Button(down_gpio, pull_up=True, bounce_time=debounce_s)

        if self.debug:
            print(f"[Buttons] LEFT={left_gpio} RIGHT={right_gpio} SELECT={select_gpio} UP={up_gpio} DOWN={down_gpio}")
            print("[Buttons] pull_up=True (press = connect to GND)")

        self.left.when_pressed = lambda: self._push("LEFT")
        self.right.when_pressed = lambda: self._push("RIGHT")
        self.select.when_pressed = lambda: self._push("SELECT")
        self.up.when_pressed = lambda: self._push("UP")
        self.down.when_pressed = lambda: self._push("DOWN")

    def _push(self, kind: str) -> None:
        ev = ButtonEvent(kind=kind, t=time.time())
        self._queue.append(ev)
        if self.debug:
            print(f"[Buttons] EVENT {kind} at {ev.t:.3f}")

    def pop_event(self) -> Optional[ButtonEvent]:
        if not self._queue:
            return None
        return self._queue.pop(0)
