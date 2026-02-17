from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

from RPLCD.i2c import CharLCD


@dataclass
class PageData:
    # What the UI needs for one station page
    stop_name: str
    direction: str              # "N" or "S"
    direction_label: str        # "Manhattan" / "Coney Island"
    arrivals: List[Tuple[str, Optional[int]]]  # [(route_id, eta_min), ...] length 0..2


class LCDUI:
    """
    20x4 LCD UI with:
      - Home page (blank)
      - Station pages from settings.json entries
      - Settings page (end)
    """
    COLS = 20
    ROWS = 4

    def __init__(self, i2c_port: int = 1, i2c_address: int = 0x27):
        self.lcd = CharLCD(
            i2c_expander="PCF8574",
            address=i2c_address,
            port=i2c_port,
            cols=self.COLS,
            rows=self.ROWS,
            charmap="A00",
            auto_linebreaks=False,
        )
        self.lcd.clear()

        # Custom chars: up arrow at code 0, down arrow at code 1
        up = [
            0b00100,
            0b01110,
            0b10101,
            0b00100,
            0b00100,
            0b00100,
            0b00100,
            0b00000,
        ]
        down = [
            0b00100,
            0b00100,
            0b00100,
            0b00100,
            0b00100,
            0b10101,
            0b01110,
            0b00100,
        ]
        self.lcd.create_char(0, up)
        self.lcd.create_char(1, down)

        # Marquee state
        self._marquee_offset = 0
        self._last_marquee_tick = 0.0

    def close(self) -> None:
        try:
            self.lcd.clear()
        finally:
            self.lcd.close()

    @staticmethod
    def _pad(s: str, width: int) -> str:
        if len(s) >= width:
            return s[:width]
        return s + (" " * (width - len(s)))

    def _marquee_18(self, text: str, tick_s: float = 0.35) -> str:
        """
        Returns an 18-char window. If text <= 18, it's padded.
        If text > 18, scrolls continuously.
        """
        now = time.time()
        if len(text) <= 18:
            self._marquee_offset = 0
            return self._pad(text, 18)

        # scroll
        if now - self._last_marquee_tick >= tick_s:
            self._last_marquee_tick = now
            self._marquee_offset = (self._marquee_offset + 1) % (len(text) + 4)  # +gap

        gap = " " * 4
        scroll_text = text + gap
        start = self._marquee_offset
        window = (scroll_text + scroll_text)[start : start + 18]
        return window

    @staticmethod
    def _arrow_char(direction: str) -> str:
        # custom chars: 0=up, 1=down
        return chr(0) if direction.upper() == "N" else chr(1)

    def render_home(self, page_idx: int, page_total: int) -> None:
        # Blank home page, but show time + page indicator on last line
        now = time.strftime("%H:%M")
        page = f"<{page_idx:2d}>"
        # You requested "< 1 >", so make it 5 chars: "< 1 >"
        page = f"< {page_idx} >".rjust(5)

        lines = [
            " " * 20,
            " " * 20,
            " " * 20,
            self._pad(now, 15) + self._pad(page, 5),
        ]
        self._write_lines(lines)

    def render_settings(self, page_idx: int, page_total: int) -> None:
        now = time.strftime("%H:%M")
        page = f"< {page_idx} >".rjust(5)

        lines = [
            self._pad("Settings", 20),
            self._pad("Select: Reload", 20),
            self._pad("L/R: Navigate", 20),
            self._pad(now, 15) + self._pad(page, 5),
        ]
        self._write_lines(lines)

    def render_station(self, data: PageData, page_idx: int, page_total: int) -> None:
        # Line 1: stop name (18 max, marquee) + space + arrow
        name18 = self._marquee_18(data.stop_name)
        arrow = self._arrow_char(data.direction)
        line1 = name18 + " " + arrow  # 18 + 1 + 1 = 20

        # Lines 2-3: "N> Manhattan      9m" (left 16, right 4)
        # left: "{route}> {direction_label}" truncated to 16
        def line_arr(i: int) -> str:
            if i >= len(data.arrivals):
                left = ""
                right = ""
            else:
                route, eta = data.arrivals[i]
                route = (route or "?").strip()[:3]
                left = f"{route}> {data.direction_label}"
                if eta is None:
                    right = "--m"
                else:
                    # right 4 chars, e.g. " 9m" or "28m"
                    right = f"{eta}m"
                # pad/right-align right field to 4
                right = right.rjust(4)

            left16 = self._pad(left, 16)
            return left16 + right  # 16 + 4

        line2 = line_arr(0)
        line3 = line_arr(1)

        # Line 4: time + page indicator at end
        now = time.strftime("%H:%M")
        page = f"< {page_idx} >".rjust(5)
        line4 = self._pad(now, 15) + self._pad(page, 5)

        self._write_lines([line1, line2, line3, line4])

    def _write_lines(self, lines: List[str]) -> None:
        # Minimal flicker: rewrite all 4 lines
        self.lcd.home()
        for r in range(self.ROWS):
            self.lcd.cursor_pos = (r, 0)
            self.lcd.write_string(self._pad(lines[r], self.COLS))
