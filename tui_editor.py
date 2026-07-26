"""Built-in terminal editor for the Kettle CLI sitting.

Uses stdlib ``curses`` only. Colors come from ``theme_catalog``; tokenization
from ``syntax``. This is intentionally a small, reliable editor for review
edits before approve — not a Vim replacement.
"""

from __future__ import annotations

import curses
import os
import signal
from dataclasses import dataclass, field
from pathlib import Path

import syntax
import theme_catalog

# Map syntax roles → curses color pair ids (1-based; 0 is default).
_PAIR = {
    "text": 1,
    "comment": 2,
    "string": 3,
    "number": 4,
    "keyword": 5,
    "storage": 5,
    "function": 6,
    "type": 4,
    "constant": 7,
    "operator": 8,
    "punctuation": 8,
    "property": 6,
    "heading": 4,
    "escape": 6,
    "invalid": 7,
    "lineno": 8,
    "status": 8,
}


def _hex_to_curses_rgb(hexv: str) -> tuple[int, int, int]:
    h = hexv.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    # curses uses 0–1000
    return r * 1000 // 255, g * 1000 // 255, b * 1000 // 255


def _nearest_ansi16(hexv: str, ansi: list[str]) -> int:
    """Fallback when terminal cannot redefine colors: map to nearest 0–15."""
    def rgb(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    tr, tg, tb = rgb(hexv)
    best_i, best_d = 7, 1e18
    for i, ah in enumerate(ansi):
        r, g, b = rgb(ah)
        d = (r - tr) ** 2 + (g - tg) ** 2 + (b - tb) ** 2
        if d < best_d:
            best_i, best_d = i, d
    return best_i


def _init_colors(pack: dict, *, dark: bool) -> None:
    curses.start_color()
    try:
        curses.use_default_colors()
    except curses.error:
        pass
    table = theme_catalog.syntax_color_table(pack, dark=dark)
    bg_hex = theme_catalog.resolve_role_hex(pack, "bg", dark=dark)
    ansi = theme_catalog.ansi_colors(pack, dark=dark)
    can_custom = curses.can_change_color() and curses.COLORS >= 16

    # pair 1..n: fg on default background (-1) for terminal-native bg
    roles = list(_PAIR.keys())
    # stable pair assignment
    role_to_pair = {r: i + 1 for i, r in enumerate(dict.fromkeys(roles))}

    if can_custom:
        # Reserve color numbers 16+ when possible, else overwrite 0-15 carefully
        base = 16 if curses.COLORS > 16 else 0
        color_ids: dict[str, int] = {}
        idx = base
        for role, hexv in table.items():
            if role not in role_to_pair:
                continue
            try:
                curses.init_color(idx, *_hex_to_curses_rgb(hexv))
                color_ids[role] = idx
                idx += 1
            except curses.error:
                color_ids[role] = _nearest_ansi16(hexv, ansi)
        try:
            bg_id = idx
            curses.init_color(bg_id, *_hex_to_curses_rgb(bg_hex))
        except curses.error:
            bg_id = -1
        for role, pair in role_to_pair.items():
            fg = color_ids.get(role, 7)
            try:
                curses.init_pair(pair, fg, -1 if bg_id < 0 else bg_id)
            except curses.error:
                curses.init_pair(pair, _nearest_ansi16(table.get(role, "#ffffff"), ansi), -1)
    else:
        for role, pair in role_to_pair.items():
            fg = _nearest_ansi16(table.get(role, "#ffffff"), ansi)
            try:
                curses.init_pair(pair, fg, -1)
            except curses.error:
                curses.init_pair(pair, 7, -1)

    # stash on module for attr()
    _init_colors.role_to_pair = role_to_pair  # type: ignore[attr-defined]


def _attr(kind: str) -> int:
    pair = getattr(_init_colors, "role_to_pair", {}).get(kind, 1)
    try:
        return curses.color_pair(pair)
    except curses.error:
        return curses.A_NORMAL


@dataclass
class Buffer:
    path: Path
    lines: list[str] = field(default_factory=list)
    row: int = 0
    col: int = 0
    row_off: int = 0
    col_off: int = 0
    dirty: bool = False
    language: str = "text"
    message: str = ""
    readonly: bool = False
    _tok_cache: list[list[tuple[str, str]]] | None = field(default=None, repr=False)
    _tok_dirty: bool = field(default=True, repr=False)

    @classmethod
    def load(cls, path: Path, *, language: str | None = None) -> Buffer:
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        lines = text.splitlines() or [""]
        lang = language or syntax.language_for_path(path)
        return cls(path=path, lines=lines, language=lang)

    def text(self) -> str:
        body = "\n".join(self.lines)
        return body + ("\n" if body and not body.endswith("\n") else "")

    def touch(self) -> None:
        self.dirty = True
        self._tok_dirty = True
        self.message = ""

    def token_lines(self) -> list[list[tuple[str, str]]]:
        if self._tok_dirty or self._tok_cache is None:
            self._tok_cache = syntax.tokenize_lines(
                "\n".join(self.lines), language=self.language,
            )
            self._tok_dirty = False
        return self._tok_cache

    def save(self) -> None:
        if self.readonly:
            self.message = "read-only"
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = "\n".join(self.lines)
        if data and not data.endswith("\n"):
            data += "\n"
        self.path.write_text(data, encoding="utf-8")
        self.dirty = False
        self.message = f"saved {self.path.name}"

    def clamp(self) -> None:
        self.row = max(0, min(self.row, len(self.lines) - 1))
        self.col = max(0, min(self.col, len(self.lines[self.row])))


def _highlighted_line(buf: Buffer, row: int) -> list[tuple[str, str]]:
    lines = buf.token_lines()
    if row < len(lines):
        return lines[row]
    return [("text", buf.lines[row] if row < len(buf.lines) else "")]


def _draw(stdscr: "curses._CursesWindow", buf: Buffer, header: str) -> None:
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()
    status_rows = 2
    text_h = max(1, max_y - status_rows)
    gutter = max(3, len(str(len(buf.lines))) + 1)

    # scroll
    if buf.row < buf.row_off:
        buf.row_off = buf.row
    if buf.row >= buf.row_off + text_h:
        buf.row_off = buf.row - text_h + 1
    if buf.col < buf.col_off:
        buf.col_off = buf.col
    if buf.col >= buf.col_off + max(1, max_x - gutter - 1):
        buf.col_off = buf.col - (max_x - gutter - 1) + 1

    for y in range(text_h):
        r = buf.row_off + y
        if r >= len(buf.lines):
            break
        # gutter
        ln = f"{r + 1}".rjust(gutter - 1) + " "
        try:
            stdscr.addstr(y, 0, ln[:max_x], _attr("lineno"))
        except curses.error:
            pass
        tokens = _highlighted_line(buf, r)
        x = gutter
        # apply horizontal scroll by skipping col_off columns of pure text width
        skip = buf.col_off
        for kind, chunk in tokens:
            for ch in chunk:
                if skip > 0:
                    skip -= 1
                    continue
                if x >= max_x:
                    break
                try:
                    stdscr.addstr(y, x, ch, _attr(kind))
                except curses.error:
                    pass
                x += 1
            if x >= max_x:
                break

    # header / status
    dirty = "*" if buf.dirty else " "
    title = f" Kettle{dirty}  {buf.path.name}  [{buf.language}]"
    if header:
        title = f" Kettle{dirty}  {header}"
    bar = title[: max_x - 1].ljust(max_x - 1)
    try:
        stdscr.addstr(max_y - 2, 0, bar, _attr("heading") | curses.A_REVERSE)
    except curses.error:
        pass
    help_l = buf.message or "^S save  ^Q quit  ^W external  arrows move  enter newline"
    try:
        stdscr.addstr(max_y - 1, 0, help_l[: max_x - 1].ljust(max_x - 1), _attr("status"))
    except curses.error:
        pass

    # cursor
    cy = buf.row - buf.row_off
    cx = gutter + (buf.col - buf.col_off)
    if 0 <= cy < text_h and gutter <= cx < max_x:
        try:
            stdscr.move(cy, cx)
        except curses.error:
            pass
    stdscr.refresh()


def _insert(buf: Buffer, s: str) -> None:
    if buf.readonly:
        buf.message = "read-only"
        return
    line = buf.lines[buf.row]
    buf.lines[buf.row] = line[: buf.col] + s + line[buf.col :]
    buf.col += len(s)
    buf.touch()


def _backspace(buf: Buffer) -> None:
    if buf.readonly:
        return
    if buf.col > 0:
        line = buf.lines[buf.row]
        buf.lines[buf.row] = line[: buf.col - 1] + line[buf.col :]
        buf.col -= 1
        buf.touch()
    elif buf.row > 0:
        prev = buf.lines[buf.row - 1]
        cur = buf.lines[buf.row]
        buf.col = len(prev)
        buf.lines[buf.row - 1] = prev + cur
        del buf.lines[buf.row]
        buf.row -= 1
        buf.touch()


def _delete(buf: Buffer) -> None:
    if buf.readonly:
        return
    line = buf.lines[buf.row]
    if buf.col < len(line):
        buf.lines[buf.row] = line[: buf.col] + line[buf.col + 1 :]
        buf.touch()
    elif buf.row + 1 < len(buf.lines):
        buf.lines[buf.row] = line + buf.lines[buf.row + 1]
        del buf.lines[buf.row + 1]
        buf.touch()


def _newline(buf: Buffer) -> None:
    if buf.readonly:
        return
    line = buf.lines[buf.row]
    buf.lines[buf.row] = line[: buf.col]
    buf.lines.insert(buf.row + 1, line[buf.col :])
    buf.row += 1
    buf.col = 0
    buf.touch()

def _run(stdscr: "curses._CursesWindow", buf: Buffer, header: str, pack: dict, dark: bool) -> int:
    curses.raw()
    curses.curs_set(1)
    stdscr.keypad(True)
    _init_colors(pack, dark=dark)

    while True:
        buf.clamp()
        _draw(stdscr, buf, header)
        ch = stdscr.get_wch()
        if isinstance(ch, str):
            o = ord(ch) if len(ch) == 1 else -1
            if o == 17:  # ^Q
                if buf.dirty and not getattr(buf, "_quit_armed", False):
                    buf._quit_armed = True  # type: ignore[attr-defined]
                    buf.message = "unsaved changes — ^Q again to discard, or ^S to save"
                    continue
                return 1 if buf.dirty else 0
            buf._quit_armed = False  # type: ignore[attr-defined]
            if o == 19:  # ^S
                try:
                    buf.save()
                except OSError as e:
                    buf.message = f"save failed: {e}"
                continue
            if o == 23:  # ^W external editor
                return 2
            if ch == "\n" or o == 10 or o == 13:
                _newline(buf)
                continue
            if o in (127, 8):  # backspace
                _backspace(buf)
                continue
            if ch.isprintable():
                _insert(buf, ch)
                continue
        else:
            buf._quit_armed = False  # type: ignore[attr-defined]
            if ch == curses.KEY_UP:
                buf.row = max(0, buf.row - 1)
            elif ch == curses.KEY_DOWN:
                buf.row = min(len(buf.lines) - 1, buf.row + 1)
            elif ch == curses.KEY_LEFT:
                if buf.col > 0:
                    buf.col -= 1
                elif buf.row > 0:
                    buf.row -= 1
                    buf.col = len(buf.lines[buf.row])
            elif ch == curses.KEY_RIGHT:
                if buf.col < len(buf.lines[buf.row]):
                    buf.col += 1
                elif buf.row + 1 < len(buf.lines):
                    buf.row += 1
                    buf.col = 0
            elif ch == curses.KEY_HOME:
                buf.col = 0
            elif ch == curses.KEY_END:
                buf.col = len(buf.lines[buf.row])
            elif ch == curses.KEY_PPAGE:
                buf.row = max(0, buf.row - 20)
            elif ch == curses.KEY_NPAGE:
                buf.row = min(len(buf.lines) - 1, buf.row + 20)
            elif ch == curses.KEY_DC:
                _delete(buf)
            elif ch == curses.KEY_BACKSPACE:
                _backspace(buf)
            elif ch == curses.KEY_ENTER:
                _newline(buf)
    return 0


def edit_file(
    path: str | Path,
    *,
    theme_id: str | None = None,
    header: str = "",
    language: str | None = None,
    dark: bool | None = None,
) -> int:
    """Open *path* in the built-in editor.

    Returns:
        0 — quit cleanly (saved or unchanged)
        1 — quit with discard of unsaved changes
        2 — caller should open external $EDITOR
        3 — curses unavailable / not a tty
    """
    path = Path(path)
    if not os.isatty(0) or not os.isatty(1):
        return 3
    pack = theme_catalog.load_theme(theme_id or theme_catalog.default_theme_id())
    if dark is None:
        dark = theme_catalog.prefer_dark_mode()
    buf = Buffer.load(path, language=language)

    # Ignore SIGINT inside the editor; ^C should not dump a traceback mid-draw.
    old = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        return curses.wrapper(lambda stdscr: _run(stdscr, buf, header, pack, dark))
    except curses.error:
        return 3
    finally:
        signal.signal(signal.SIGINT, old)
