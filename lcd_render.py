from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Union
from PIL import Image, ImageDraw

# -----------------------------
# Types
# -----------------------------
CharCode = Union[str, int]  # normal character like "A" OR custom-char index 0..7

@dataclass
class LCDStyle:
    cols: int = 20
    rows: int = 4

    # Character cell geometry (HD44780-like)
    dot_w: int = 4          # size of a single dot (square)
    dot_h: int = 4
    dot_gap_x: int = 1      # spacing between dots inside a char
    dot_gap_y: int = 1
    char_gap_x: int = 2     # spacing between characters
    char_gap_y: int = 2
    border: int = 12        # padding around the LCD area

    # Colors
    bg: Tuple[int, int, int] = (0, 100, 200)        # LCD background
    dot_on: Tuple[int, int, int] = (235, 245, 255)  # lit pixel
    dot_off: Tuple[int, int, int] = (30, 90, 160)   # unlit pixel (for grid look)
    frame: Tuple[int, int, int] = (0, 0, 0)         # outer frame

    # Optional grid effect
    show_dot_grid: bool = True
    frame_thickness: int = 10
    corner_radius: int = 12


# -----------------------------
# Minimal 5x8 font (ASCII subset)
# Each glyph is 8 rows of 5 bits.
# Unknown chars render as blank.
# You can extend this dictionary as needed.
# -----------------------------
def build_font_5x8_ascii() -> Dict[str, List[int]]:
    """
    Returns FONT_5x8 for ASCII 0x20..0x7E (95 chars).
    Each glyph: 8 rows, 5 bits per row.
    """
    # Public-domain style 5x8 ASCII font (classic terminal/LCD look)
    # Index 0 corresponds to ASCII 0x20 (' '), index 94 -> 0x7E ('~')
    data: List[List[int]] = [
        # 0x20 ' '
        [0,0,0,0,0,0,0,0],
        # 0x21 '!'
        [0b00100,0b00100,0b00100,0b00100,0b00100,0,0b00100,0],
        # 0x22 '"'
        [0b01010,0b01010,0b01010,0,0,0,0,0],
        # 0x23 '#'
        [0b01010,0b01010,0b11111,0b01010,0b11111,0b01010,0b01010,0],
        # 0x24 '$'
        [0b00100,0b01111,0b10100,0b01110,0b00101,0b11110,0b00100,0],
        # 0x25 '%'
        [0b11001,0b11010,0b00100,0b01000,0b10110,0b00110,0,0],
        # 0x26 '&'
        [0b01100,0b10010,0b10100,0b01000,0b10101,0b10010,0b01101,0],
        # 0x27 "'"
        [0b00100,0b00100,0b01000,0,0,0,0,0],
        # 0x28 '('
        [0b00010,0b00100,0b01000,0b01000,0b01000,0b00100,0b00010,0],
        # 0x29 ')'
        [0b01000,0b00100,0b00010,0b00010,0b00010,0b00100,0b01000,0],
        # 0x2A '*'
        [0,0b00100,0b10101,0b01110,0b10101,0b00100,0,0],
        # 0x2B '+'
        [0,0b00100,0b00100,0b11111,0b00100,0b00100,0,0],
        # 0x2C ','
        [0,0,0,0,0b00110,0b00110,0b00100,0b01000],
        # 0x2D '-'
        [0,0,0,0b11111,0,0,0,0],
        # 0x2E '.'
        [0,0,0,0,0,0b00110,0b00110,0],
        # 0x2F '/'
        [0b00001,0b00010,0b00100,0b01000,0b10000,0,0,0],
        # 0x30 '0'
        [0b01110,0b10001,0b10011,0b10101,0b11001,0b10001,0b01110,0],
        # 0x31 '1'
        [0b00100,0b01100,0b00100,0b00100,0b00100,0b00100,0b01110,0],
        # 0x32 '2'
        [0b01110,0b10001,0b00001,0b00010,0b00100,0b01000,0b11111,0],
        # 0x33 '3'
        [0b11111,0b00010,0b00100,0b00010,0b00001,0b10001,0b01110,0],
        # 0x34 '4'
        [0b00010,0b00110,0b01010,0b10010,0b11111,0b00010,0b00010,0],
        # 0x35 '5'
        [0b11111,0b10000,0b10000,0b11110,0b00001,0b00001,0b11110,0],
        # 0x36 '6'
        [0b00110,0b01000,0b10000,0b11110,0b10001,0b10001,0b01110,0],
        # 0x37 '7'
        [0b11111,0b00001,0b00010,0b00100,0b01000,0b01000,0b01000,0],
        # 0x38 '8'
        [0b01110,0b10001,0b10001,0b01110,0b10001,0b10001,0b01110,0],
        # 0x39 '9'
        [0b01110,0b10001,0b10001,0b01111,0b00001,0b00010,0b01100,0],
        # 0x3A ':'
        [0,0b01100,0b01100,0,0,0b01100,0b01100,0],
        # 0x3B ';'
        [0,0b00100,0b00100,0,0b00100,0b00100,0b01000,0],
        # 0x3C '<'
        [0b00010,0b00100,0b01000,0b10000,0b01000,0b00100,0b00010,0],
        # 0x3D '='
        [0,0,0b11111,0,0b11111,0,0,0],
        # 0x3E '>'
        [0b01000,0b00100,0b00010,0b00001,0b00010,0b00100,0b01000,0],
        # 0x3F '?'
        [0b01110,0b10001,0b00001,0b00010,0b00100,0,0b00100,0],
        # 0x40 '@'
        [0b01110,0b10001,0b00001,0b01101,0b10101,0b10101,0b01110,0],
        # 0x41 'A'
        [0b01110,0b10001,0b10001,0b11111,0b10001,0b10001,0b10001,0],
        # 0x42 'B'
        [0b11110,0b10001,0b10001,0b11110,0b10001,0b10001,0b11110,0],
        # 0x43 'C'
        [0b01110,0b10001,0b10000,0b10000,0b10000,0b10001,0b01110,0],
        # 0x44 'D'
        [0b11110,0b10001,0b10001,0b10001,0b10001,0b10001,0b11110,0],
        # 0x45 'E'
        [0b11111,0b10000,0b10000,0b11110,0b10000,0b10000,0b11111,0],
        # 0x46 'F'
        [0b11111,0b10000,0b10000,0b11110,0b10000,0b10000,0b10000,0],
        # 0x47 'G'
        [0b01110,0b10001,0b10000,0b10111,0b10001,0b10001,0b01110,0],
        # 0x48 'H'
        [0b10001,0b10001,0b10001,0b11111,0b10001,0b10001,0b10001,0],
        # 0x49 'I'
        [0b01110,0b00100,0b00100,0b00100,0b00100,0b00100,0b01110,0],
        # 0x4A 'J'
        [0b00111,0b00010,0b00010,0b00010,0b00010,0b10010,0b01100,0],
        # 0x4B 'K'
        [0b10001,0b10010,0b10100,0b11000,0b10100,0b10010,0b10001,0],
        # 0x4C 'L'
        [0b10000,0b10000,0b10000,0b10000,0b10000,0b10000,0b11111,0],
        # 0x4D 'M'
        [0b10001,0b11011,0b10101,0b10101,0b10001,0b10001,0b10001,0],
        # 0x4E 'N'
        [0b10001,0b11001,0b10101,0b10011,0b10001,0b10001,0b10001,0],
        # 0x4F 'O'
        [0b01110,0b10001,0b10001,0b10001,0b10001,0b10001,0b01110,0],
        # 0x50 'P'
        [0b11110,0b10001,0b10001,0b11110,0b10000,0b10000,0b10000,0],
        # 0x51 'Q'
        [0b01110,0b10001,0b10001,0b10001,0b10101,0b10010,0b01101,0],
        # 0x52 'R'
        [0b11110,0b10001,0b10001,0b11110,0b10100,0b10010,0b10001,0],
        # 0x53 'S'
        [0b01111,0b10000,0b10000,0b01110,0b00001,0b00001,0b11110,0],
        # 0x54 'T'
        [0b11111,0b00100,0b00100,0b00100,0b00100,0b00100,0b00100,0],
        # 0x55 'U'
        [0b10001,0b10001,0b10001,0b10001,0b10001,0b10001,0b01110,0],
        # 0x56 'V'
        [0b10001,0b10001,0b10001,0b10001,0b10001,0b01010,0b00100,0],
        # 0x57 'W'
        [0b10001,0b10001,0b10001,0b10101,0b10101,0b10101,0b01010,0],
        # 0x58 'X'
        [0b10001,0b10001,0b01010,0b00100,0b01010,0b10001,0b10001,0],
        # 0x59 'Y'
        [0b10001,0b10001,0b01010,0b00100,0b00100,0b00100,0b00100,0],
        # 0x5A 'Z'
        [0b11111,0b00001,0b00010,0b00100,0b01000,0b10000,0b11111,0],
        # 0x5B '['
        [0b01110,0b01000,0b01000,0b01000,0b01000,0b01000,0b01110,0],
        # 0x5C '\'
        [0b10000,0b01000,0b00100,0b00010,0b00001,0,0,0],
        # 0x5D ']'
        [0b01110,0b00010,0b00010,0b00010,0b00010,0b00010,0b01110,0],
        # 0x5E '^'
        [0b00100,0b01010,0b10001,0,0,0,0,0],
        # 0x5F '_'
        [0,0,0,0,0,0,0b11111,0],
        # 0x60 '`'
        [0b01000,0b00100,0b00010,0,0,0,0,0],
        # 0x61 'a'
        [0,0,0b01110,0b00001,0b01111,0b10001,0b01111,0],
        # 0x62 'b'
        [0b10000,0b10000,0b11110,0b10001,0b10001,0b10001,0b11110,0],
        # 0x63 'c'
        [0,0,0b01110,0b10001,0b10000,0b10001,0b01110,0],
        # 0x64 'd'
        [0b00001,0b00001,0b01111,0b10001,0b10001,0b10001,0b01111,0],
        # 0x65 'e'
        [0,0,0b01110,0b10001,0b11111,0b10000,0b01110,0],
        # 0x66 'f'
        [0b00110,0b01000,0b11110,0b01000,0b01000,0b01000,0b01000,0],
        # 0x67 'g'
        [0,0,0b01111,0b10001,0b10001,0b01111,0b00001,0b01110],
        # 0x68 'h'
        [0b10000,0b10000,0b11110,0b10001,0b10001,0b10001,0b10001,0],
        # 0x69 'i'
        [0,0b00100,0,0b01100,0b00100,0b00100,0b01110,0],
        # 0x6A 'j'
        [0,0b00010,0,0b00010,0b00010,0b10010,0b10010,0b01100],
        # 0x6B 'k'
        [0b10000,0b10000,0b10010,0b10100,0b11000,0b10100,0b10010,0],
        # 0x6C 'l'
        [0b01100,0b00100,0b00100,0b00100,0b00100,0b00100,0b01110,0],
        # 0x6D 'm'
        [0,0,0b11010,0b10101,0b10101,0b10001,0b10001,0],
        # 0x6E 'n'
        [0,0,0b11110,0b10001,0b10001,0b10001,0b10001,0],
        # 0x6F 'o'
        [0,0,0b01110,0b10001,0b10001,0b10001,0b01110,0],
        # 0x70 'p'
        [0,0,0b11110,0b10001,0b10001,0b11110,0b10000,0b10000],
        # 0x71 'q'
        [0,0,0b01111,0b10001,0b10001,0b01111,0b00001,0b00001],
        # 0x72 'r'
        [0,0,0b10110,0b11001,0b10000,0b10000,0b10000,0],
        # 0x73 's'
        [0,0,0b01111,0b10000,0b01110,0b00001,0b11110,0],
        # 0x74 't'
        [0b01000,0b01000,0b11100,0b01000,0b01000,0b01001,0b00110,0],
        # 0x75 'u'
        [0,0,0b10001,0b10001,0b10001,0b10011,0b01101,0],
        # 0x76 'v'
        [0,0,0b10001,0b10001,0b10001,0b01010,0b00100,0],
        # 0x77 'w'
        [0,0,0b10001,0b10001,0b10101,0b10101,0b01010,0],
        # 0x78 'x'
        [0,0,0b10001,0b01010,0b00100,0b01010,0b10001,0],
        # 0x79 'y'
        [0,0,0b10001,0b10001,0b01111,0b00001,0b01110,0],
        # 0x7A 'z'
        [0,0,0b11111,0b00010,0b00100,0b01000,0b11111,0],
        # 0x7B '{'
        [0b00010,0b00100,0b00100,0b01000,0b00100,0b00100,0b00010,0],
        # 0x7C '|'
        [0b00100,0b00100,0b00100,0,0b00100,0b00100,0b00100,0],
        # 0x7D '}'
        [0b01000,0b00100,0b00100,0b00010,0b00100,0b00100,0b01000,0],
        # 0x7E '~'
        [0,0,0b01001,0b10110,0,0,0,0],
    ]

    font: Dict[str, List[int]] = {}
    for i, rows8 in enumerate(data):
        ch = chr(0x20 + i)
        font[ch] = rows8
    return font

FONT_5x8 = build_font_5x8_ascii()

def glyph_from_rows(rows8: List[int]) -> List[int]:
    """Convert 8 row bitmasks (5 bits each) to the same format (already rows)."""
    if len(rows8) != 8:
        raise ValueError("glyph must be 8 rows")
    return rows8


# -----------------------------
# LCD Renderer
# -----------------------------
class LCDRenderer:
    def __init__(self, style: LCDStyle):
        self.s = style

    def _cell_px(self) -> Tuple[int, int]:
        # 5 dots wide, 8 dots high
        w = 5 * self.s.dot_w + 4 * self.s.dot_gap_x
        h = 8 * self.s.dot_h + 7 * self.s.dot_gap_y
        return w, h

    def _canvas_size(self) -> Tuple[int, int]:
        cell_w, cell_h = self._cell_px()
        w = self.s.border * 2 + self.s.cols * cell_w + (self.s.cols - 1) * self.s.char_gap_x
        h = self.s.border * 2 + self.s.rows * cell_h + (self.s.rows - 1) * self.s.char_gap_y
        # plus frame thickness around (drawn outside LCD area visually)
        w += self.s.frame_thickness * 2
        h += self.s.frame_thickness * 2
        return w, h

    def render(
        self,
        lines: List[List[CharCode]],
        *,
        custom_chars: Optional[Dict[int, List[int]]] = None,
        outfile: Optional[str] = None,
    ) -> Image.Image:
        """
        lines: rows x cols, each entry is:
          - normal str length 1 (ASCII glyph)
          - int 0..7 for custom chars
        custom_chars: mapping {index: rows8}, rows8 is 8 ints, each int has 5 bits (0..31)
        """
        if len(lines) != self.s.rows:
            raise ValueError(f"Expected {self.s.rows} rows")
        for r in lines:
            if len(r) != self.s.cols:
                raise ValueError(f"Each row must have {self.s.cols} cols")

        custom_chars = custom_chars or {}

        W, H = self._canvas_size()
        img = Image.new("RGB", (W, H), self.s.frame)
        draw = ImageDraw.Draw(img)

        # inner LCD area rect
        fx = self.s.frame_thickness
        fy = self.s.frame_thickness
        iw = W - 2 * self.s.frame_thickness
        ih = H - 2 * self.s.frame_thickness

        # rounded LCD “glass”
        try:
            draw.rounded_rectangle(
                [fx, fy, fx + iw, fy + ih],
                radius=self.s.corner_radius,
                fill=self.s.bg,
                outline=self.s.frame,
                width=2,
            )
        except Exception:
            draw.rectangle([fx, fy, fx + iw, fy + ih], fill=self.s.bg)

        cell_w, cell_h = self._cell_px()

        # start position inside glass
        x0 = fx + self.s.border
        y0 = fy + self.s.border

        for row in range(self.s.rows):
            for col in range(self.s.cols):
                ch = lines[row][col]
                gx = x0 + col * (cell_w + self.s.char_gap_x)
                gy = y0 + row * (cell_h + self.s.char_gap_y)

                # fetch glyph rows (8 rows of 5-bit masks)
                if isinstance(ch, int):
                    rows8 = custom_chars.get(ch, [0]*8)
                else:
                    rows8 = FONT_5x8.get(ch, FONT_5x8.get(" ", [0]*8))

                # draw dots
                for r in range(8):
                    mask = rows8[r] & 0b11111
                    for c in range(5):
                        bit = (mask >> (4 - c)) & 1
                        px = gx + c * (self.s.dot_w + self.s.dot_gap_x)
                        py = gy + r * (self.s.dot_h + self.s.dot_gap_y)
                        color = self.s.dot_on if bit else (self.s.dot_off if self.s.show_dot_grid else self.s.bg)
                        draw.rectangle([px, py, px + self.s.dot_w - 1, py + self.s.dot_h - 1], fill=color)

        if outfile:
            img.save(outfile)
        return img


# -----------------------------
# Helper: build a screen from strings + inline custom codes
# -----------------------------
def make_screen(cols: int, rows: int, text_rows: List[str]) -> List[List[CharCode]]:
    """
    Convert list of strings to rows of length cols. Strings can include:
      - normal characters
      - '\x00'..'\x07' to represent custom characters 0..7
    """
    out: List[List[CharCode]] = []
    for r in range(rows):
        s = text_rows[r] if r < len(text_rows) else ""
        s = s[:cols].ljust(cols)
        row: List[CharCode] = []
        for ch in s:
            oc = ord(ch)
            if 0 <= oc <= 7:
                row.append(oc)
            else:
                row.append(ch)
        out.append(row)
    return out


if __name__ == "__main__":
    # Your 8 custom characters (rows of 5 bits)
    # NOTE: these are the same row arrays you used in RPLCD create_char()
    # Here we convert each row (0b.....) to 5-bit values (already 5-bit).
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
        0b00100, 0b01110, 0b11111, 0b10101,
        0b10101, 0b10101, 0b11111, 0b00000,
    ]
    sun = [
        0b00100, 0b10101, 0b01110, 0b11111,
        0b01110, 0b10101, 0b00100, 0b00000,
    ]
    cloud = [
        0b00000, 0b00000, 0b01110, 0b11111,
        0b11111, 0b11111, 0b01110, 0b00000,
    ]
    rain = [
        0b00000, 0b01110, 0b11111, 0b11111,
        0b11111, 0b10101, 0b01010, 0b00000,
    ]
    snow = [
        0b00000, 0b01010, 0b00100, 0b11111,
        0b00100, 0b01010, 0b00000, 0b00000,
    ]

    custom = {
        0: up,
        1: down,
        2: heart,
        3: home,
        4: sun,
        5: cloud,
        6: rain,
        7: snow,
    }

    style = LCDStyle(
        cols=20, rows=4,
        dot_w=4, dot_h=4,
        dot_gap_x=1, dot_gap_y=1,
        char_gap_x=2, char_gap_y=2,
        border=12,
        bg=(0, 120, 210),
        dot_on=(240, 250, 255),
        dot_off=(25, 95, 165),
        show_dot_grid=True,
        frame=(0, 0, 0),
        frame_thickness=12,
        corner_radius=14,
    )

    r = LCDRenderer(style)

    # Example screen using:
    # - weather icon: custom char 5 (cloud)
    # - heart: custom char 2
    # - home icon: custom char 3
    # screen = make_screen(
    #     20, 4,
    #     [
    #         "\x05 Overcast PoP:  02%",   # icon + text
    #         "Temp.: 01C Feel:-04C",
    #         "Leave in 05 min",
    #         "13:12          < \x03 >"     # heart in pager spot
    #     ]
    # )

    screen = make_screen(
        20, 4,
        [
            "\x07 Overcast PoP:  02%",   # icon + text
            "Temp.: 01C Feel:-04C",
            "Leave in 05 min",
            "13:12          < \x03 >"     # heart in pager spot
        ]
    )

    img = r.render(screen, custom_chars=custom, outfile="lcd_preview.png")
    print("Wrote lcd_preview.png")
