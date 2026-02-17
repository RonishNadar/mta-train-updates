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
        Big time charset (font: square_four) based on the provided C code.

        Custom chars 0..7 correspond to:
        square_four_00 .. square_four_07
        """
        if self._charset_mode == self._CHARSET_BIG:
            return
        self._charset_mode = self._CHARSET_BIG

        # Direct port of the C arrays:
        # const byte square_four_00[8] = {B11111,B11111,B11100,B11100,B00000,B00000,B00000,B00000};
        square_four_00 = [
            0b11111,
            0b11111,
            0b11100,
            0b11100,
            0b00000,
            0b00000,
            0b00000,
            0b00000,
        ]

        # const byte square_four_01[8] = {B00000,B00000,B00000,B00000,B11100,B11100,B11111,B11111};
        square_four_01 = [
            0b00000,
            0b00000,
            0b00000,
            0b00000,
            0b11100,
            0b11100,
            0b11111,
            0b11111,
        ]

        # const byte square_four_02[8] = {B11111,B11111,B01111,B01111,B01111,B01111,B11111,B11111};
        square_four_02 = [
            0b11111,
            0b11111,
            0b01111,
            0b01111,
            0b01111,
            0b01111,
            0b11111,
            0b11111,
        ]

        # const byte square_four_03[8] = {B11111,B11111,B11110,B11110,B11110,B11110,B11111,B11111};
        square_four_03 = [
            0b11111,
            0b11111,
            0b11110,
            0b11110,
            0b11110,
            0b11110,
            0b11111,
            0b11111,
        ]

        # const byte square_four_04[8] = {B00001,B00011,B00111,B01111,B00000,B00000,B00000,B00000};
        square_four_04 = [
            0b00001,
            0b00011,
            0b00111,
            0b01111,
            0b00000,
            0b00000,
            0b00000,
            0b00000,
        ]

        # const byte square_four_05[8] = {B11110,B11110,B11110,B11110,B11110,B11110,B11110,B11110};
        square_four_05 = [
            0b11110,
            0b11110,
            0b11110,
            0b11110,
            0b11110,
            0b11110,
            0b11110,
            0b11110,
        ]

        # const byte square_four_06[8] = {B11111,B11111,B00000,B00000,B00000,B00000,B11111,B11111};
        square_four_06 = [
            0b11111,
            0b11111,
            0b00000,
            0b00000,
            0b00000,
            0b00000,
            0b11111,
            0b11111,
        ]

        # const byte square_four_07[8] = {B11110,B11110,B11110,B11110,B11110,B11110,B11111,B11111};
        square_four_07 = [
            0b11110,
            0b11110,
            0b11110,
            0b11110,
            0b11110,
            0b11110,
            0b11111,
            0b11111,
        ]

        # Load into CGRAM slots 0..7
        self.lcd.create_char(0, square_four_00)
        self.lcd.create_char(1, square_four_01)
        self.lcd.create_char(2, square_four_02)
        self.lcd.create_char(3, square_four_03)
        self.lcd.create_char(4, square_four_04)
        self.lcd.create_char(5, square_four_05)
        self.lcd.create_char(6, square_four_06)
        self.lcd.create_char(7, square_four_07)


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
        square_four font digit:
        returns [row0, row1], each is 2 characters wide.
        Uses Arduino mapping:
        square_four_digits[10][4] =
        {
            {255,255,3,2}, {4,5,254,5}, {6,2,3,6}, {0,2,1,2}, {7,1,254,5},
            {3,6,6,2}, {3,6,3,2}, {0,2,254,5}, {3,2,3,2}, {3,2,6,2}
        }
        Where:
        255 = full block (use chr(255))
        254 = empty (use space)
        0..7 = custom chars (use chr(n))
        """
        # digit tile table from Arduino code
        # order: [top-left, top-right, bottom-left, bottom-right]
        square_four_digits = {
            "0": (255, 255, 3, 2),
            "1": (4, 5, 254, 5),
            "2": (6, 2, 3, 6),
            "3": (0, 2, 1, 2),
            "4": (7, 1, 254, 5),
            "5": (3, 6, 6, 2),
            "6": (3, 6, 3, 2),
            "7": (0, 2, 254, 5),
            "8": (3, 2, 3, 2),
            "9": (3, 2, 6, 2),
        }

        tiles = square_four_digits.get(str(d), (254, 254, 254, 254))
        tl, tr, bl, br = tiles

        def to_char(v: int) -> str:
            if v == 254:
                return " "          # empty
            if v == 255:
                return chr(255)     # full block in HD44780 ROM
            return chr(v)           # custom char 0..7

        row0 = to_char(tl) + to_char(tr)
        row1 = to_char(bl) + to_char(br)
        return [row0, row1]


    # -------------------- RENDERERS --------------------

    def render_home(self, page_idx: int) -> None:
        self._load_charset_big()

        hhmm = time.strftime("%H:%M")  # note the colon included
        # Format: "HH:MM"
        H1, H2, _, M1, M2 = hhmm[0], hhmm[1], hhmm[2], hhmm[3], hhmm[4]

        d0 = self._big_digit(H1)
        d1 = self._big_digit(H2)
        d2 = self._big_digit(M1)
        d3 = self._big_digit(M2)

        # Use normal ':' character between hours and minutes
        # Total width: 2+2+1+2+2 = 9 chars
        row0 = d0[0] + d1[0] + ":" + d2[0] + d3[0]
        row1 = d0[1] + d1[1] + " " + d2[1] + d3[1]   # space aligns better than ':' on bottom row

        pad_left = max(0, (20 - len(row0)) // 2)
        row0 = self._pad((" " * pad_left) + row0, 20)
        row1 = self._pad((" " * pad_left) + row1, 20)

        now_small = time.strftime("%H:%M")
        # In square_four charset, slot 7 is NOT "home" anymore (it is square_four_07).
        # So for bottom-right, use nav charset OR just show "< H >" with plain H.
        # Best: keep it plain to avoid charset conflicts:
        page = "< H >".rjust(5)
        line4 = self._pad(now_small, 15) + self._pad(page, 5)

        self._write_lines([row0, row1, " " * 20, line4])


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
