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

        # Cache previous lines to avoid rewriting the LCD constantly (I2C is slow)
        self._last_lines = [""] * self.ROWS

        self._marquee_offset = 0
        self._last_marquee_tick = 0.0

        # Track which set of custom chars is loaded (CGRAM has only 8 slots)
        self._charset_mode: Optional[str] = None

        # Default to normal UI charset
        self._load_charset_nav()

    def close(self) -> None:
        try:
            self.lcd.clear()
        finally:
            self.lcd.close()

    # -------------------- CHARSETS --------------------

    def _load_charset_nav(self) -> None:
        """
        NAV charset:
          0 up, 1 down, 2 heart, 3 home
          4..7 unused
        """
        if self._charset_mode == "nav":
            return
        self._charset_mode = "nav"

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

        self.lcd.create_char(0, up)
        self.lcd.create_char(1, down)
        self.lcd.create_char(2, heart)
        self.lcd.create_char(3, home)

    def _load_charset_home(self) -> None:
        """
        HOME charset (NAV + weather icons):
          0 up, 1 down, 2 heart, 3 home
          4 sun, 5 cloud, 6 rain, 7 snow
        """
        if self._charset_mode == "home":
            return
        self._charset_mode = "home"

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

        # Simple 5x8 weather icons
        sun = [
            0b00100,
            0b10101,
            0b01110,
            0b11111,
            0b01110,
            0b10101,
            0b00100,
            0b00000,
        ]
        cloud = [
            0b00000,
            0b00000,
            0b01110,
            0b11111,
            0b11111,
            0b11111,
            0b01110,
            0b00000,
        ]
        rain = [
            0b00000,
            0b01110,
            0b11111,
            0b11111,
            0b11111,
            0b10101,
            0b01010,
            0b00000,
        ]
        snow = [
            0b00000,
            0b01010,
            0b00100,
            0b11111,
            0b00100,
            0b01010,
            0b00000,
            0b00000,
        ]

        self.lcd.create_char(0, up)
        self.lcd.create_char(1, down)
        self.lcd.create_char(2, heart)
        self.lcd.create_char(3, home)
        self.lcd.create_char(4, sun)
        self.lcd.create_char(5, cloud)
        self.lcd.create_char(6, rain)
        self.lcd.create_char(7, snow)

    # -------------------- HELPERS --------------------

    @staticmethod
    def _pad(s: str, width: int) -> str:
        return (s[:width] + (" " * width))[:width]

    def _write_lines(self, lines: List[str]) -> None:
        # Normalize to exactly 4 padded lines
        norm = [self._pad(lines[i], self.COLS) for i in range(self.ROWS)]

        # Write only lines that changed
        for r in range(self.ROWS):
            if norm[r] != self._last_lines[r]:
                self.lcd.cursor_pos = (r, 0)
                self.lcd.write_string(norm[r])
                self._last_lines[r] = norm[r]

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

    @staticmethod
    def _home_char() -> str:
        return chr(3)

    @staticmethod
    def _weather_icon_kind(kind: str) -> str:
        """
        Maps weather kind -> custom char.
        slots: 4 sun, 5 cloud, 6 rain, 7 snow
        """
        k = (kind or "").lower()
        if "sun" in k or "clear" in k:
            return chr(4)
        if "snow" in k or "sleet" in k:
            return chr(7)
        if "rain" in k or "shower" in k or "drizzle" in k or "storm" in k:
            return chr(6)
        # default
        return chr(5)

    @staticmethod
    def _fmt_int_or_dash(x: Optional[float]) -> str:
        if x is None:
            return "--"
        return str(int(round(x)))

    # -------------------- RENDERERS --------------------

    def render_home(
        self,
        page_idx: int,
        weather_kind: str,
        weather_text: str,
        pop_pct: Optional[int],
        temp_val: Optional[float],
        feels_val: Optional[float],
        temp_unit: str,  # "C" or "F"
    ) -> None:
        """
        Home page target format:
        Row1: [icon] Overcast PoP:  02%
        Row2: Temp.:-20C Feel:-04C
        Row3: blank
        Row4: HH:MM + < home >
        """
        self._load_charset_home()

        icon = self._weather_icon_kind(weather_kind)

        # Row1
        cond = (weather_text or "-").strip()
        cond = cond[:10]  # keep similar to your example

        # Pop shown as 2 digits, aligned like: "PoP:  02%"
        if pop_pct is None:
            pop2 = "--"
        else:
            pop2 = f"{int(pop_pct) % 100:02d}"
        line1 = f"{icon} {cond} PoP:{pop2:>4}%"
        line1 = self._pad(line1, 20)

        # Row2: Temp.:-20C Feel:-04C  (exactly 20 chars ideally)
        unit = (temp_unit or "C").upper()
        unit = "F" if unit == "F" else "C"

        def fmt2(v: Optional[float]) -> str:
            if v is None:
                return "--"
            n = int(round(v))
            # render -04, 05, 20
            if n < 0:
                return f"-{abs(n):02d}"
            return f"{n:02d}"

        t = fmt2(temp_val)
        f = fmt2(feels_val)
        line2 = f"Temp.:{t}{unit} Feel:{f}{unit}"
        line2 = self._pad(line2, 20)

        line3 = " " * 20

        # Row4
        now = time.strftime("%H:%M")
        home = self._home_char()
        page = f"< {home} >".rjust(5)
        line4 = self._pad(now, 15) + self._pad(page, 5)

        self._write_lines([line1, line2, line3, line4])


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

    def render_wifi_list_page(self, networks: List[str], active_ssid: str, selected_idx: int, status: str = "") -> None:
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
