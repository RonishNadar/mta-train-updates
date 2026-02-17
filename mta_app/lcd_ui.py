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

    # Charset modes for the 8 CGRAM custom chars
    _CHARSET_NAV = "nav"   # arrows/heart + home icon
    _CHARSET_BIG = "big"   # big time charset (digits + colon + home icon)

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

        # Cache previous lines to avoid rewriting the LCD constantly (I2C is slow)
        self._last_lines = [""] * self.ROWS

        # Marquee state
        self._marquee_offset = 0
        self._last_marquee_tick = 0.0

        # Track which charset is currently loaded
        self._charset_mode: Optional[str] = None

        # Load default nav charset (arrows/heart/home)
        self._load_charset_nav()

    def close(self) -> None:
        try:
            self.lcd.clear()
        finally:
            self.lcd.close()

    # -------------------- CHARSETS --------------------

    def _load_charset_nav(self) -> None:
        """Normal UI charset: Up, Down, Heart, Home."""
        if self._charset_mode == self._CHARSET_NAV:
            return
        self._charset_mode = self._CHARSET_NAV

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
        # simple home icon (fits in 5x8)
        home = [
            0b00100,
            0b01110,
            0b11111,
            0b10101,
            0b10101,
            0b10101,
            0b11111,
            0b00000,
        ]

        # 0=up, 1=down, 2=heart, 3=home
        self.lcd.create_char(0, up)
        self.lcd.create_char(1, down)
        self.lcd.create_char(2, heart)
        self.lcd.create_char(3, home)

    def _load_charset_big(self) -> None:
        """
        Big time charset:
          0..5 = big digit blocks
          6    = colon
          7    = home icon (for < H > on home page)
        """
        if self._charset_mode == self._CHARSET_BIG:
            return
        self._charset_mode = self._CHARSET_BIG

        # Big digit blocks (2-row)
        ul = [
            0b11111, 0b11111, 0b11000, 0b11000,
            0b11000, 0b11000, 0b11000, 0b11000,
        ]
        um = [
            0b11111, 0b11111, 0b00000, 0b00000,
            0b00000, 0b00000, 0b00000, 0b00000,
        ]
        ur = [
            0b11111, 0b11111, 0b00011, 0b00011,
            0b00011, 0b00011, 0b00011, 0b00011,
        ]
        ll = [
            0b11000, 0b11000, 0b11000, 0b11000,
            0b11000, 0b11000, 0b11111, 0b11111,
        ]
        lm = [
            0b00000, 0b00000, 0b00000, 0b00000,
            0b00000, 0b00000, 0b11111, 0b11111,
        ]
        lr = [
            0b00011, 0b00011, 0b00011, 0b00011,
            0b00011, 0b00011, 0b11111, 0b11111,
        ]
        colon = [
            0b00000,
            0b00100,
            0b00100,
            0b00000,
            0b00000,
            0b00100,
            0b00100,
            0b00000,
        ]
        home = [
            0b00100,
            0b01110,
            0b11111,
            0b10101,
            0b10101,
            0b10101,
            0b11111,
            0b00000,
        ]

        self.lcd.create_char(0, ul)
        self.lcd.create_char(1, um)
        self.lcd.create_char(2, ur)
        self.lcd.create_char(3, ll)
        self.lcd.create_char(4, lm)
        self.lcd.create_char(5, lr)
        self.lcd.create_char(6, colon)
        self.lcd.create_char(7, home)

    # -------------------- HELPERS --------------------

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
        # nav charset: 0=up, 1=down
        return chr(0) if direction.upper() == "N" else chr(1)

    @staticmethod
    def _heart_char() -> str:
        # nav charset: 2=heart
        return chr(2)

    @staticmethod
    def _home_char_nav() -> str:
        # nav charset: 3=home
        return chr(3)

    # -------------------- BIG TIME --------------------

    def _big_digit(self, d: str) -> List[str]:
        """
        Returns [row0, row1] each 3 chars wide using big charset chars 0..5.
        """
        sp = " "
        UL, UM, UR = chr(0), chr(1), chr(2)
        LL, LM, LR = chr(3), chr(4), chr(5)

        digits = {
            "0": [UL + UM + UR, LL + LM + LR],
            "1": [sp + UR + sp, sp + LR + sp],
            "2": [sp + UM + UR, LL + LM + sp],
            "3": [sp + UM + UR, sp + LM + LR],
            "4": [UL + sp + UR, sp + sp + LR],
            "5": [UL + UM + sp, sp + LM + LR],
            "6": [UL + UM + sp, LL + LM + LR],
            "7": [sp + UM + UR, sp + sp + LR],
            "8": [UL + UM + UR, LL + LM + LR],
            "9": [UL + UM + UR, sp + LM + LR],
        }
        return digits.get(d, [sp * 3, sp * 3])

    # -------------------- RENDERERS --------------------

    def render_home(self, page_idx: int) -> None:
        """
        Home page:
          - 2-row big time (HH:MM)
          - bottom-right shows "< H >" with a custom Home icon
        """
        self._load_charset_big()

        hhmm = time.strftime("%H%M")
        HH = hhmm[:2]
        MM = hhmm[2:]

        d0 = self._big_digit(HH[0])
        d1 = self._big_digit(HH[1])
        d2 = self._big_digit(MM[0])
        d3 = self._big_digit(MM[1])

        colon = chr(6)  # big charset colon
        row0 = d0[0] + d1[0] + colon + d2[0] + d3[0]
        row1 = d0[1] + d1[1] + colon + d2[1] + d3[1]

        # Center into 20 cols
        pad_left = max(0, (20 - len(row0)) // 2)
        row0 = self._pad((" " * pad_left) + row0, 20)
        row1 = self._pad((" " * pad_left) + row1, 20)

        now_small = time.strftime("%H:%M")
        home_icon = chr(7)  # big charset home icon at slot 7
        page = f"< {home_icon} >".rjust(5)
        line4 = self._pad(now_small, 15) + self._pad(page, 5)

        lines = [
            row0,
            row1,
            " " * 20,
            line4,
        ]
        self._write_lines(lines)

    def render_station(self, data: PageData, page_idx: int) -> None:
        self._load_charset_nav()

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
        self._load_charset_nav()

        now = time.strftime("%H:%M")
        heart = self._heart_char()
        page = f"< {heart} >".rjust(5)

        lines = [
            self._pad("Settings:", 20),
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
        self._load_charset_nav()

        items = ["IP address", "Wi Fi", "Select stations", "About"]
        selected_idx = max(0, min(selected_idx, len(items) - 1))

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
        self._load_charset_nav()

        now = time.strftime("%H:%M")
        lines = [
            self._pad("IP address:", 20),
            self._pad(f"IP: {ip_address}", 20),
            self._pad("Left: Back", 20),
            self._pad(now, 20),
        ]
        self._write_lines(lines)

    def render_about_page(self) -> None:
        self._load_charset_nav()

        now = time.strftime("%H:%M")
        lines = [
            self._pad("About:", 20),
            self._pad("Project by", 20),
            self._pad("Ronish Nadar", 20),
            self._pad(now, 20),
        ]
        self._write_lines(lines)

    def render_web_config_page(self, url: str) -> None:
        self._load_charset_nav()

        now = time.strftime("%H:%M")
        lines = [
            self._pad("Select stations:", 20),
            self._pad("Open:", 20),
            self._pad(url, 20),
            self._pad(now, 20),
        ]
        self._write_lines(lines)

    def render_wifi_list_page(
        self,
        networks: List[str],
        active_ssid: str,
        selected_idx: int,
        status: str = "",
    ) -> None:
        self._load_charset_nav()

        now = time.strftime("%H:%M")
        bottom = status if status else now

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
        self._load_charset_nav()

        cursor = max(0, min(cursor, 15))

        shown = (password + (" " * 16))[:16]
        caret_line = " " * cursor + "^" + " " * (19 - cursor)

        lines = [
            self._pad(f"WiFi: {ssid}"[:20], 20),
            self._pad(shown, 20),
            self._pad(caret_line, 20),
            self._pad("Sel=OK  L=Back", 20),
        ]
        self._write_lines(lines)

    def _write_lines(self, lines: List[str]) -> None:
        # Normalize to exactly 4 padded lines
        norm = [self._pad(lines[i], self.COLS) for i in range(self.ROWS)]

        # Write only lines that changed
        for r in range(self.ROWS):
            if norm[r] != self._last_lines[r]:
                self.lcd.cursor_pos = (r, 0)
                self.lcd.write_string(norm[r])
                self._last_lines[r] = norm[r]
