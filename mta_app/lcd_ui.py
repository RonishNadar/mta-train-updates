from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

from RPLCD.i2c import CharLCD


@dataclass
class PageData:
    stop_name: str
    direction: str
    direction_label: str
    arrivals: List[Tuple[str, Optional[int]]]  # [(route_id, eta_min)] up to 2


class LCDUI:
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

        # Custom chars:
        # 0=up arrow, 1=down arrow, 2=heart
        up = [
            0b00100, 0b01110, 0b10101, 0b00100,
            0b00100, 0b00100, 0b00100, 0b00000,
        ]
        down = [
            0b00100, 0b00100, 0b00100, 0b00100,
            0b00100, 0b10101, 0b01110, 0b00100,
        ]
        heart = [
            0b00000, 0b01010, 0b11111, 0b11111,
            0b11111, 0b01110, 0b00100, 0b00000,
        ]
        self.lcd.create_char(0, up)
        self.lcd.create_char(1, down)
        self.lcd.create_char(2, heart)

        self._marquee_offset = 0
        self._last_marquee_tick = 0.0

    def close(self) -> None:
        try:
            self.lcd.clear()
        finally:
            self.lcd.close()

    @staticmethod
    def _pad(s: str, width: int) -> str:
        return (s[:width] + (" " * width))[:width]

    def _marquee_18(self, text: str, tick_s: float = 0.35) -> str:
        now = time.time()
        if len(text) <= 18:
            self._marquee_offset = 0
            return self._pad(text, 18)

        if now - self._last_marquee_tick >= tick_s:
            self._last_marquee_tick = now
            self._marquee_offset = (self._marquee_offset + 1) % (len(text) + 4)

        gap = " " * 4
        scroll_text = text + gap
        start = self._marquee_offset
        window = (scroll_text + scroll_text)[start : start + 18]
        return window

    @staticmethod
    def _arrow_char(direction: str) -> str:
        return chr(0) if direction.upper() == "N" else chr(1)

    @staticmethod
    def _heart_char() -> str:
        return chr(2)

    def render_home(self, page_idx: int) -> None:
        now = time.strftime("%H:%M")
        page = f"< {page_idx} >".rjust(5)
        lines = [
            " " * 20,
            " " * 20,
            " " * 20,
            self._pad(now, 15) + self._pad(page, 5),
        ]
        self._write_lines(lines)

    def render_station(self, data: PageData, page_idx: int) -> None:
        name18 = self._marquee_18(data.stop_name)
        arrow = self._arrow_char(data.direction)
        line1 = name18 + " " + arrow

        def fmt_line(i: int) -> str:
            if i >= len(data.arrivals):
                left, right = "", ""
            else:
                route, eta = data.arrivals[i]
                route = (route or "?").strip()[:3]
                left = f"{route}> {data.direction_label}"
                right = ("--m" if eta is None else f"{eta}m").rjust(4)
            return self._pad(left, 16) + right

        line2 = fmt_line(0)
        line3 = fmt_line(1)

        now = time.strftime("%H:%M")
        page = f"< {page_idx} >".rjust(5)
        line4 = self._pad(now, 15) + self._pad(page, 5)

        self._write_lines([line1, line2, line3, line4])

    # -------- SETTINGS HUB + SUBPAGES --------

    def render_settings_landing(self, page_idx: int) -> None:
        now = time.strftime("%H:%M")
        heart = self._heart_char()
        page = f"< {heart} >".rjust(5)

        lines = [
            self._pad("Settings", 20),
            self._pad("Press Select", 20),
            self._pad("L/R: Pages", 20),
            self._pad(now, 15) + self._pad(page, 5),
        ]
        self._write_lines(lines)


    def render_settings_menu(self, selected_idx: int, page_idx: int) -> None:
        """
        4 items across 3 lines (scroll window of 3).
        Up/Down moves selection. Select enters.
        """
        items = ["IP address", "Wi Fi", "Select stations", "About"]
        selected_idx = max(0, min(selected_idx, len(items) - 1))

        # Window start so selected stays visible in 3 lines
        start = max(0, min(selected_idx - 1, len(items) - 3))
        window = items[start : start + 3]

        lines = [self._pad("> Settings", 20)]
        for i, label in enumerate(window):
            abs_idx = start + i
            prefix = ">" if abs_idx == selected_idx else " "
            lines.append(self._pad(f"{prefix} {label}", 20))

        now = time.strftime("%H:%M")
        heart = self._heart_char()
        page = f"< {heart} >".rjust(5)
        lines.append(self._pad(now, 15) + self._pad(page, 5))

        self._write_lines(lines)

    def render_ip_page(self, ip_address: str) -> None:
        now = time.strftime("%H:%M")
        lines = [
            self._pad("IP address:", 20),
            self._pad(f"IP: {ip_address}", 20),
            self._pad("Left: Back", 20),
            self._pad(now, 20),
        ]
        self._write_lines(lines)

    def render_about_page(self) -> None:
        now = time.strftime("%H:%M")
        lines = [
            self._pad("About:", 20),
            self._pad("Project by", 20),
            self._pad("Ronish Nadar", 20),
            self._pad(now, 20),
        ]
        self._write_lines(lines)

    def render_web_config_page(self, url: str) -> None:
        """
        Shows link user should open from phone/laptop on same Wi-Fi.
        """
        now = time.strftime("%H:%M")
        lines = [
            self._pad("Select stations:", 20),
            self._pad("Open:", 20),
            self._pad(url, 20),
            self._pad(now, 20),
        ]
        self._write_lines(lines)

    def render_wifi_list_page(self, networks: List[str], active_ssid: str, selected_idx: int, status: str = "") -> None:
        """
        20x4:
        L1: Wi Fi:
        L2: >* SSID
        L3:  * SSID
        L4: status or time
        """
        now = time.strftime("%H:%M")

        if status:
            bottom = status
        else:
            bottom = now

        if not networks:
            lines = [
                self._pad("Wi Fi:", 20),
                self._pad("No networks", 20),
                self._pad("Left: Back", 20),
                self._pad(bottom, 20),
            ]
            self._write_lines(lines)
            return

        selected_idx = max(0, min(selected_idx, len(networks) - 1))
        start = max(0, min(selected_idx, len(networks) - 2))
        win = networks[start : start + 2]

        lines = [self._pad("Wi Fi:", 20)]

        for i in range(2):
            if i < len(win):
                ssid = win[i]
                abs_idx = start + i
                prefix = ">" if abs_idx == selected_idx else " "
                mark = "*" if ssid == active_ssid and ssid else " "
                lines.append(self._pad(f"{prefix}{mark} {ssid}", 20))
            else:
                lines.append(" " * 20)

        lines.append(self._pad(bottom, 20))
        self._write_lines(lines)


    def render_wifi_password_page(self, ssid: str, password: str, cursor: int) -> None:
        """
        Password entry:
          - Up/Down changes current character
          - Left/Right moves cursor
          - Select confirms
        """
        now = time.strftime("%H:%M")
        cursor = max(0, min(cursor, 15))

        # Show password as visible characters (you can switch to '*' if you prefer)
        shown = (password + (" " * 16))[:16]
        # Put a caret on next line at cursor
        caret_line = " " * cursor + "^" + " " * (19 - cursor)

        lines = [
            self._pad(f"WiFi: {ssid}"[:20], 20),
            self._pad(shown, 20),
            self._pad(caret_line, 20),
            self._pad("Sel=OK  L=Back", 20),
        ]
        self._write_lines(lines)

    def _write_lines(self, lines: List[str]) -> None:
        # Cache previous lines to avoid rewriting the LCD constantly (I2C is slow)
        if not hasattr(self, "_last_lines"):
            self._last_lines = [""] * self.ROWS

        # Normalize to exactly 4 padded lines
        norm = [self._pad(lines[i], self.COLS) for i in range(self.ROWS)]

        # Write only lines that changed
        for r in range(self.ROWS):
            if norm[r] != self._last_lines[r]:
                self.lcd.cursor_pos = (r, 0)
                self.lcd.write_string(norm[r])
                self._last_lines[r] = norm[r]

