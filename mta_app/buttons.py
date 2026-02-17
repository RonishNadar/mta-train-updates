# mta_app/buttons.py
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional
from queue import SimpleQueue

from gpiozero import Button


@dataclass
class ButtonEvent:
    kind: str
    t: float


class Buttons:
    def __init__(
        self,
        left_gpio: int,
        right_gpio: int,
        select_gpio: int,
        up_gpio: int,
        down_gpio: int,
        *,
        pull_up: bool = True,
        bounce_s: float = 0.05,
        select_hold_s: float = 3.0,
    ):
        self.q: SimpleQueue[ButtonEvent] = SimpleQueue()

        print(f"[Buttons] LEFT={left_gpio} RIGHT={right_gpio} SELECT={select_gpio} UP={up_gpio} DOWN={down_gpio}")
        print(f"[Buttons] pull_up={pull_up} (press = connect to GND)")

        self.left = Button(left_gpio, pull_up=pull_up, bounce_time=bounce_s)
        self.right = Button(right_gpio, pull_up=pull_up, bounce_time=bounce_s)
        self.select = Button(select_gpio, pull_up=pull_up, bounce_time=bounce_s, hold_time=select_hold_s, hold_repeat=False)
        self.up = Button(up_gpio, pull_up=pull_up, bounce_time=bounce_s)
        self.down = Button(down_gpio, pull_up=pull_up, bounce_time=bounce_s)

        self.left.when_pressed = lambda: self._push("LEFT")
        self.right.when_pressed = lambda: self._push("RIGHT")
        self.select.when_pressed = lambda: self._push("SELECT")
        self.select.when_held = lambda: self._push("SELECT_LONG")
        self.up.when_pressed = lambda: self._push("UP")
        self.down.when_pressed = lambda: self._push("DOWN")

    def _push(self, kind: str) -> None:
        self.q.put(ButtonEvent(kind=kind, t=time.time()))

    def pop_event(self) -> Optional[ButtonEvent]:
        try:
            return self.q.get_nowait()
        except Exception:
            return None
