"""A YAML subset for rubric front matter and scenario files.

Supported: mappings, sequences, plain and quoted scalars, ``|`` and ``>`` block
scalars, and full-line comments. Tabs are rejected. This is not a general YAML
loader — scenario files in this tree stay inside the subset.
"""

from __future__ import annotations

import re

_BLOCK = re.compile(
    r"^(?P<key>[^:#]+?):\s*(?P<style>[|>])(?P<chomp>[+-]?)\s*(?:#.*)?$"
)


class YAMLError(ValueError):
    def __init__(self, message: str, line: int | None = None):
        self.line = line
        if line:
            message = f"line {line}: {message}"
        super().__init__(message)


def loads(text: str):
    """Parse a subset YAML document into dicts, lists, and scalars."""
    events = _scan(text)
    if not events:
        return None
    kind = events[0][1]
    indent = events[0][0]
    if kind == "key":
        value, idx = _parse_map(events, 0, indent)
    elif kind in ("item", "item-key"):
        value, idx = _parse_seq(events, 0, indent)
    else:
        raise YAMLError(f"cannot start a document with {kind}", events[0][3])
    if idx != len(events):
        raise YAMLError("trailing content", events[idx][3])
    return value


def _scan(text: str) -> list[tuple]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.split("\n")
    events: list[tuple] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        lineno = i + 1
        if raw.strip() == "" or raw.lstrip().startswith("#"):
            i += 1
            continue
        if raw.startswith("\t") or "\t" in raw[: len(raw) - len(raw.lstrip(" "))]:
            raise YAMLError("tabs are not allowed for indent", lineno)
        indent = len(raw) - len(raw.lstrip(" "))
        content = raw.strip()
        if content.startswith("- "):
            rest = content[2:].strip()
            block = _BLOCK.match(rest)
            if block:
                key = block.group("key").strip()
                block_lines, i = _read_block(lines, i + 1, indent)
                text_value = _compose_block(
                    block_lines, block.group("style"), block.group("chomp") or ""
                )
                events.append((indent, "item-key", (key, text_value), lineno))
                continue
            if ": " in rest or (rest.endswith(":") and not rest.startswith('"')):
                events.append((indent, "item-key", _split_key(rest, lineno), lineno))
            else:
                events.append((indent, "item", _scalar(rest), lineno))
            i += 1
            continue
        block = _BLOCK.match(content)
        if block:
            key = block.group("key").strip()
            block_lines, i = _read_block(lines, i + 1, indent)
            text_value = _compose_block(
                block_lines, block.group("style"), block.group("chomp") or ""
            )
            events.append((indent, "key", (key, text_value), lineno))
            continue
        if ":" not in content:
            raise YAMLError(f"expected a key or list item, got {content!r}", lineno)
        events.append((indent, "key", _split_key(content, lineno), lineno))
        i += 1
    return events


def _read_block(lines: list[str], i: int, parent_indent: int) -> tuple[list[str], int]:
    block: list[str] = []
    while i < len(lines):
        raw = lines[i]
        if raw.strip() == "":
            block.append("")
            i += 1
            continue
        if raw.startswith("\t"):
            raise YAMLError("tabs are not allowed for indent", i + 1)
        indent = len(raw) - len(raw.lstrip(" "))
        if indent <= parent_indent:
            break
        block.append(raw)
        i += 1
    while block and block[-1] == "":
        block.pop()
    return block, i


def _compose_block(block: list[str], style: str, chomp: str) -> str:
    if not block:
        return ""
    indents = [
        len(line) - len(line.lstrip(" ")) for line in block if line.strip() != ""
    ]
    base = min(indents) if indents else 0
    parts: list[str] = []
    for line in block:
        if line.strip() == "":
            parts.append("")
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent < base:
            raise YAMLError("block scalar is indented less than its first line")
        parts.append(line[base:])
    if style == "|":
        text = "\n".join(parts)
    else:
        paragraphs: list[str] = []
        current: list[str] = []
        for part in parts:
            if part == "":
                if current:
                    paragraphs.append(" ".join(current))
                    current = []
            else:
                current.append(part)
        if current:
            paragraphs.append(" ".join(current))
        text = "\n".join(paragraphs)
    if chomp == "-":
        return text
    return text + ("\n" if text else "")


def _split_key(content: str, line: int) -> tuple[str, object]:
    if content.endswith(":") and ": " not in content:
        key = content[:-1].strip()
        if not key:
            raise YAMLError("empty key", line)
        return key, None
    idx = content.find(": ")
    if idx == -1:
        raise YAMLError(f"expected 'key: value', got {content!r}", line)
    key = content[:idx].strip()
    if not key:
        raise YAMLError("empty key", line)
    return key, _scalar(content[idx + 2 :].strip())


def _scalar(raw: str):
    if raw in ("", "~", "null", "Null"):
        return None
    if raw in ("true", "True"):
        return True
    if raw in ("false", "False"):
        return False
    if re.fullmatch(r"-?(0|[1-9]\d*)", raw):
        return int(raw)
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return _unquote(raw)
    return raw


def _unquote(raw: str) -> str:
    quote = raw[0]
    body = raw[1:-1]
    if quote == "'":
        return body.replace("''", "'")
    out: list[str] = []
    i = 0
    while i < len(body):
        if body[i] != "\\":
            out.append(body[i])
            i += 1
            continue
        if i + 1 >= len(body):
            raise YAMLError("dangling escape in a double-quoted string")
        nxt = body[i + 1]
        mapping = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "r": "\r"}
        if nxt not in mapping:
            raise YAMLError(f"unsupported escape \\{nxt}")
        out.append(mapping[nxt])
        i += 2
    return "".join(out)


def _parse_map(events: list[tuple], i: int, indent: int) -> tuple[dict, int]:
    mapping: dict = {}
    while i < len(events):
        ev_indent, kind, payload, line = events[i]
        if ev_indent < indent or kind != "key":
            break
        if ev_indent > indent:
            raise YAMLError("unexpected indent", line)
        key, val = payload
        if key in mapping:
            raise YAMLError(f"duplicate key {key!r}", line)
        i += 1
        val, i = _fill_nested(events, i, indent, val)
        mapping[key] = val
    return mapping, i


def _parse_seq(events: list[tuple], i: int, indent: int) -> tuple[list, int]:
    seq: list = []
    while i < len(events):
        ev_indent, kind, payload, line = events[i]
        if ev_indent < indent:
            break
        if ev_indent > indent:
            raise YAMLError("unexpected indent", line)
        if kind == "item":
            seq.append(payload)
            i += 1
            continue
        if kind != "item-key":
            break
        key, val = payload
        i += 1
        item: dict = {}
        val, i = _fill_nested(events, i, ev_indent, val)
        item[key] = val
        while i < len(events) and events[i][0] > ev_indent and events[i][1] == "key":
            key_indent, _, key_payload, key_line = events[i]
            child_key, child_val = key_payload
            if child_key in item:
                raise YAMLError(f"duplicate key {child_key!r}", key_line)
            i += 1
            child_val, i = _fill_nested(events, i, key_indent, child_val)
            item[child_key] = child_val
        seq.append(item)
    return seq, i


def _fill_nested(events: list[tuple], i: int, parent_indent: int, val):
    if val is not None or i >= len(events) or events[i][0] <= parent_indent:
        return val, i
    child_kind = events[i][1]
    child_indent = events[i][0]
    if child_kind in ("item", "item-key"):
        return _parse_seq(events, i, child_indent)
    if child_kind == "key":
        return _parse_map(events, i, child_indent)
    raise YAMLError(f"cannot nest {child_kind}", events[i][3])
