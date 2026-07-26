"""Stdlib syntax highlighters for the built-in CLI editor and shared tools.

Token kinds match ``theme_catalog.SYNTAX_ROLE_DEFAULTS`` so colors stay on the
active theme pack. This is not a full TextMate engine — it aims for clear,
fast coloring of the languages Kettle desks see most often.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Iterable

# (kind, text) — kind is a syntax role name
Token = tuple[str, str]
Tokenizer = Callable[[str], list[Token]]


def language_for_path(path: str | Path | None) -> str:
    if not path:
        return "text"
    name = Path(path).name.lower()
    if name in {"dockerfile", "makefile", "gemfile", "rakefile", "procfile"}:
        return {
            "dockerfile": "dockerfile",
            "makefile": "shell",
            "gemfile": "ruby",
            "rakefile": "ruby",
            "procfile": "shell",
        }[name]
    suf = Path(path).suffix.lower()
    return {
        ".py": "python",
        ".pyi": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".json": "json",
        ".jsonc": "json",
        ".md": "markdown",
        ".markdown": "markdown",
        ".mdx": "markdown",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".toml": "toml",
        ".ini": "ini",
        ".cfg": "ini",
        ".css": "css",
        ".scss": "css",
        ".less": "css",
        ".html": "html",
        ".htm": "html",
        ".xml": "html",
        ".svg": "html",
        ".sh": "shell",
        ".bash": "shell",
        ".zsh": "shell",
        ".fish": "shell",
        ".rs": "rust",
        ".go": "go",
        ".rb": "ruby",
        ".java": "java",
        ".kt": "kotlin",
        ".c": "c",
        ".h": "c",
        ".cc": "cpp",
        ".cpp": "cpp",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".php": "php",
        ".sql": "sql",
        ".r": "r",
        ".lua": "lua",
        ".swift": "swift",
        ".vue": "html",
        ".svelte": "html",
    }.get(suf, "text")


def tokenize(text: str, *, language: str | None = None, path: str | Path | None = None) -> list[Token]:
    lang = language or language_for_path(path)
    fn = TOKENIZERS.get(lang) or tokenize_text
    return fn(text)


def tokenize_lines(
    text: str,
    *,
    language: str | None = None,
    path: str | Path | None = None,
) -> list[list[Token]]:
    """Tokenize a full buffer, then split into per-line token lists (no trailing \\n in tokens)."""
    tokens = tokenize(text, language=language, path=path)
    lines: list[list[Token]] = [[]]
    for kind, chunk in tokens:
        parts = chunk.split("\n")
        for i, part in enumerate(parts):
            if i:
                lines.append([])
            if part:
                lines[-1].append((kind, part))
    # Ensure at least one line for empty files
    if not lines:
        lines = [[]]
    return lines


# ── generic helpers ──────────────────────────────────────────────────────────

def _emit_plain(s: str, kind: str = "text") -> list[Token]:
    return [(kind, s)] if s else []


def _scan_generic(
    text: str,
    *,
    keywords: set[str],
    line_comment: str | None = "#",
    block_comment: tuple[str, str] | None = None,
    string_delims: Iterable[str] = ('"', "'"),
) -> list[Token]:
    out: list[Token] = []
    i, n = 0, len(text)
    ident = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    number = re.compile(r"0[xX][0-9A-Fa-f]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
    while i < n:
        # block comment
        if block_comment and text.startswith(block_comment[0], i):
            end = text.find(block_comment[1], i + len(block_comment[0]))
            if end < 0:
                out.append(("comment", text[i:]))
                break
            end += len(block_comment[1])
            out.append(("comment", text[i:end]))
            i = end
            continue
        # line comment
        if line_comment and text.startswith(line_comment, i):
            j = text.find("\n", i)
            if j < 0:
                out.append(("comment", text[i:]))
                break
            out.append(("comment", text[i:j]))
            i = j
            continue
        # strings
        matched_str = False
        for d in string_delims:
            if text.startswith(d, i):
                j = i + len(d)
                while j < n:
                    if text[j] == "\\":
                        j = min(n, j + 2)
                        continue
                    if text.startswith(d, j):
                        j += len(d)
                        break
                    j += 1
                out.append(("string", text[i:j]))
                i = j
                matched_str = True
                break
        if matched_str:
            continue
        # number
        m = number.match(text, i)
        if m:
            out.append(("number", m.group(0)))
            i = m.end()
            continue
        # ident / keyword
        m = ident.match(text, i)
        if m:
            word = m.group(0)
            kind = "keyword" if word in keywords else "text"
            # crude function: ident followed by (
            k = m.end()
            while k < n and text[k] in " \t":
                k += 1
            if k < n and text[k] == "(" and word not in keywords:
                kind = "function"
            out.append((kind, word))
            i = m.end()
            continue
        # operators / punctuation
        ch = text[i]
        if ch in "{}[](),.;:?":
            out.append(("punctuation", ch))
            i += 1
            continue
        if ch in "+-*/%<>=!&|^~":
            j = i + 1
            while j < n and text[j] in "+-*/%<>=!&|^~":
                j += 1
            out.append(("operator", text[i:j]))
            i = j
            continue
        out.append(("text", ch))
        i += 1
    return out


# ── language tokenizers ──────────────────────────────────────────────────────

_PY_KW = {
    "False", "None", "True", "and", "as", "assert", "async", "await", "break",
    "class", "continue", "def", "del", "elif", "else", "except", "finally",
    "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
    "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
    "match", "case", "type",
}


def tokenize_python(text: str) -> list[Token]:
    out: list[Token] = []
    i, n = 0, len(text)
    ident = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    number = re.compile(r"0[xX][0-9A-Fa-f]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
    while i < n:
        if text.startswith("#", i):
            j = text.find("\n", i)
            out.append(("comment", text[i:] if j < 0 else text[i:j]))
            i = n if j < 0 else j
            continue
        # triple strings
        for d in ('"""', "'''"):
            if text.startswith(d, i):
                j = text.find(d, i + 3)
                if j < 0:
                    out.append(("string", text[i:]))
                    return out
                out.append(("string", text[i:j + 3]))
                i = j + 3
                break
        else:
            if text[i] in "\"'":
                d = text[i]
                j = i + 1
                while j < n:
                    if text[j] == "\\":
                        j = min(n, j + 2)
                        continue
                    if text[j] == d:
                        j += 1
                        break
                    j += 1
                out.append(("string", text[i:j]))
                i = j
                continue
            m = number.match(text, i)
            if m:
                out.append(("number", m.group(0)))
                i = m.end()
                continue
            m = ident.match(text, i)
            if m:
                word = m.group(0)
                if word in _PY_KW:
                    kind = "keyword"
                elif word in {"self", "cls"}:
                    kind = "constant"
                else:
                    k = m.end()
                    while k < n and text[k] in " \t":
                        k += 1
                    kind = "function" if k < n and text[k] == "(" else "text"
                    if word[:1].isupper() and "_" not in word[:1]:
                        # Type-ish CapWords
                        if kind == "text":
                            kind = "type"
                out.append((kind, word))
                i = m.end()
                continue
            ch = text[i]
            if ch in "{}[](),.;:":
                out.append(("punctuation", ch))
            elif ch in "+-*/%<>=!&|^~@":
                j = i + 1
                while j < n and text[j] in "+-*/%<>=!&|^~@":
                    j += 1
                out.append(("operator", text[i:j]))
                i = j
                continue
            else:
                out.append(("text", ch))
            i += 1
    return out


_JS_KW = {
    "break", "case", "catch", "class", "const", "continue", "debugger", "default",
    "delete", "do", "else", "export", "extends", "false", "finally", "for",
    "function", "if", "import", "in", "instanceof", "let", "new", "null",
    "return", "super", "switch", "this", "throw", "true", "try", "typeof",
    "undefined", "var", "void", "while", "with", "yield", "async", "await",
    "of", "from", "as", "static", "get", "set", "enum", "implements",
    "interface", "package", "private", "protected", "public", "readonly",
    "type", "namespace", "declare", "abstract", "satisfies", "keyof", "infer",
}


def tokenize_javascript(text: str) -> list[Token]:
    return _scan_generic(
        text,
        keywords=_JS_KW,
        line_comment="//",
        block_comment=("/*", "*/"),
        string_delims=('"', "'", "`"),
    )


def tokenize_json(text: str) -> list[Token]:
    out: list[Token] = []
    i, n = 0, len(text)
    number = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
    while i < n:
        if text[i] in " \t\r\n":
            out.append(("text", text[i]))
            i += 1
            continue
        if text[i] == '"':
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j = min(n, j + 2)
                    continue
                if text[j] == '"':
                    j += 1
                    break
                j += 1
            # property vs string value: look ahead for :
            k = j
            while k < n and text[k] in " \t\r\n":
                k += 1
            kind = "property" if k < n and text[k] == ":" else "string"
            out.append((kind, text[i:j]))
            i = j
            continue
        m = number.match(text, i)
        if m:
            out.append(("number", m.group(0)))
            i = m.end()
            continue
        if text.startswith("true", i) or text.startswith("false", i) or text.startswith("null", i):
            for lit in ("true", "false", "null"):
                if text.startswith(lit, i):
                    out.append(("constant", lit))
                    i += len(lit)
                    break
            continue
        if text[i] in "{}[],:":
            out.append(("punctuation", text[i]))
            i += 1
            continue
        out.append(("text", text[i]))
        i += 1
    return out


def tokenize_markdown(text: str) -> list[Token]:
    out: list[Token] = []
    fence = False
    for line in text.splitlines(keepends=True):
        raw = line
        if re.match(r"^\s*(```|~~~)", line):
            fence = not fence
            out.append(("punctuation", line))
            continue
        if fence:
            out.append(("string", line))
            continue
        if re.match(r"^#{1,6}\s", line):
            out.append(("heading", line))
            continue
        if re.match(r"^\s*([-*+]|\d+\.)\s", line):
            m = re.match(r"^(\s*(?:[-*+]|\d+\.)\s+)(.*)$", line, re.S)
            if m:
                out.append(("operator", m.group(1)))
                out.extend(_inline_md(m.group(2)))
                continue
        if re.match(r"^\s*>\s?", line):
            out.append(("comment", line))
            continue
        out.extend(_inline_md(line))
    return out


def _inline_md(s: str) -> list[Token]:
    out: list[Token] = []
    i, n = 0, len(s)
    while i < n:
        if s.startswith("**", i):
            j = s.find("**", i + 2)
            if j >= 0:
                out.append(("heading", s[i:j + 2]))
                i = j + 2
                continue
        if s[i] == "`":
            j = s.find("`", i + 1)
            if j >= 0:
                out.append(("string", s[i:j + 1]))
                i = j + 1
                continue
        if s.startswith("[", i):
            j = s.find("]", i + 1)
            if j >= 0 and j + 1 < n and s[j + 1] == "(":
                k = s.find(")", j + 2)
                if k >= 0:
                    out.append(("keyword", s[i:k + 1]))
                    i = k + 1
                    continue
        out.append(("text", s[i]))
        i += 1
    return out


def tokenize_yaml(text: str) -> list[Token]:
    out: list[Token] = []
    for line in text.splitlines(keepends=True):
        if re.match(r"^\s*#", line):
            out.append(("comment", line))
            continue
        if re.match(r"^\s*---\s*$", line) or re.match(r"^\s*\.\.\.\s*$", line):
            out.append(("heading", line))
            continue
        m = re.match(r"^(\s*)([\w.-]+)(\s*:\s*)(.*)$", line, re.S)
        if m:
            out.append(("text", m.group(1)))
            out.append(("property", m.group(2)))
            out.append(("punctuation", m.group(3)))
            rest = m.group(4)
            if rest.lstrip().startswith("#"):
                out.append(("comment", rest))
            elif re.match(r'^\s*["\']', rest):
                out.append(("string", rest))
            elif re.match(r"^\s*(\d+|true|false|null)\s*$", rest, re.I):
                out.append(("number" if rest.strip().isdigit() else "constant", rest))
            else:
                out.append(("text", rest))
            continue
        m = re.match(r"^(\s*-\s+)(.*)$", line, re.S)
        if m:
            out.append(("operator", m.group(1)))
            out.append(("text", m.group(2)))
            continue
        out.append(("text", line))
    return out


def tokenize_shell(text: str) -> list[Token]:
    return _scan_generic(
        text,
        keywords={
            "if", "then", "else", "elif", "fi", "for", "while", "do", "done",
            "case", "esac", "function", "return", "in", "select", "time",
            "coproc", "[[", "]]",
        },
        line_comment="#",
        string_delims=('"', "'", "`"),
    )


def tokenize_css(text: str) -> list[Token]:
    return _scan_generic(
        text,
        keywords={
            "important", "from", "to", "and", "or", "not", "only",
        },
        line_comment=None,
        block_comment=("/*", "*/"),
        string_delims=('"', "'"),
    )


def tokenize_html(text: str) -> list[Token]:
    out: list[Token] = []
    i, n = 0, len(text)
    while i < n:
        if text.startswith("<!--", i):
            j = text.find("-->", i + 4)
            if j < 0:
                out.append(("comment", text[i:]))
                break
            out.append(("comment", text[i:j + 3]))
            i = j + 3
            continue
        if text[i] == "<":
            j = text.find(">", i + 1)
            if j < 0:
                out.append(("keyword", text[i:]))
                break
            out.append(("keyword", text[i:j + 1]))
            i = j + 1
            continue
        j = text.find("<", i)
        if j < 0:
            out.append(("text", text[i:]))
            break
        out.append(("text", text[i:j]))
        i = j
    return out


def tokenize_toml(text: str) -> list[Token]:
    out: list[Token] = []
    for line in text.splitlines(keepends=True):
        if re.match(r"^\s*#", line):
            out.append(("comment", line))
            continue
        if re.match(r"^\s*\[", line):
            out.append(("heading", line))
            continue
        m = re.match(r"^(\s*)([\w.-]+)(\s*=\s*)(.*)$", line, re.S)
        if m:
            out.append(("text", m.group(1)))
            out.append(("property", m.group(2)))
            out.append(("operator", m.group(3)))
            rest = m.group(4)
            if rest.lstrip().startswith(("'", '"')):
                out.append(("string", rest))
            else:
                out.append(("text", rest))
            continue
        out.append(("text", line))
    return out


def tokenize_text(text: str) -> list[Token]:
    return _emit_plain(text, "text")


# C-family and others via generic keyword sets
_C_KW = {
    "auto", "break", "case", "char", "const", "continue", "default", "do",
    "double", "else", "enum", "extern", "float", "for", "goto", "if", "int",
    "long", "register", "return", "short", "signed", "sizeof", "static",
    "struct", "switch", "typedef", "union", "unsigned", "void", "volatile",
    "while", "class", "namespace", "template", "typename", "public", "private",
    "protected", "virtual", "override", "new", "delete", "this", "true", "false",
    "nullptr", "bool", "using", "try", "catch", "throw",
}
_GO_KW = {
    "break", "case", "chan", "const", "continue", "default", "defer", "else",
    "fallthrough", "for", "func", "go", "goto", "if", "import", "interface",
    "map", "package", "range", "return", "select", "struct", "switch", "type",
    "var",
}
_RS_KW = {
    "as", "async", "await", "break", "const", "continue", "crate", "dyn",
    "else", "enum", "extern", "false", "fn", "for", "if", "impl", "in", "let",
    "loop", "match", "mod", "move", "mut", "pub", "ref", "return", "self",
    "Self", "static", "struct", "super", "trait", "true", "type", "unsafe",
    "use", "where", "while",
}
_SQL_KW = {
    "select", "from", "where", "and", "or", "not", "insert", "into", "values",
    "update", "set", "delete", "create", "table", "index", "drop", "alter",
    "join", "left", "right", "inner", "outer", "on", "as", "group", "by",
    "order", "limit", "offset", "having", "union", "all", "distinct", "null",
    "true", "false", "case", "when", "then", "else", "end",
}


def _c_like(text: str, keywords: set[str]) -> list[Token]:
    return _scan_generic(
        text, keywords=keywords, line_comment="//",
        block_comment=("/*", "*/"), string_delims=('"', "'"),
    )


TOKENIZERS: dict[str, Tokenizer] = {
    "python": tokenize_python,
    "javascript": tokenize_javascript,
    "typescript": tokenize_javascript,
    "json": tokenize_json,
    "markdown": tokenize_markdown,
    "yaml": tokenize_yaml,
    "shell": tokenize_shell,
    "css": tokenize_css,
    "html": tokenize_html,
    "toml": tokenize_toml,
    "ini": tokenize_toml,
    "c": lambda t: _c_like(t, _C_KW),
    "cpp": lambda t: _c_like(t, _C_KW),
    "csharp": lambda t: _c_like(t, _C_KW | {"async", "await", "var", "string"}),
    "java": lambda t: _c_like(t, _C_KW | {"package", "import", "extends", "implements"}),
    "kotlin": lambda t: _c_like(t, _C_KW | {"fun", "val", "var", "when", "object", "companion"}),
    "go": lambda t: _c_like(t, _GO_KW),
    "rust": lambda t: _c_like(t, _RS_KW),
    "ruby": lambda t: _scan_generic(t, keywords={"def", "class", "module", "end", "if", "else", "elsif", "unless", "while", "do", "yield", "return", "require", "include", "attr_reader", "attr_writer", "attr_accessor", "true", "false", "nil"}, line_comment="#", string_delims=('"', "'")),
    "php": lambda t: _scan_generic(t, keywords={"function", "class", "public", "private", "protected", "return", "if", "else", "elseif", "while", "for", "foreach", "as", "echo", "new", "use", "namespace", "true", "false", "null"}, line_comment="//", block_comment=("/*", "*/"), string_delims=('"', "'")),
    "sql": lambda t: _scan_generic(t, keywords=_SQL_KW, line_comment="--", block_comment=("/*", "*/"), string_delims=("'")),
    "swift": lambda t: _c_like(t, _C_KW | {"func", "let", "var", "guard", "import", "protocol", "extension", "nil", "self"}),
    "lua": lambda t: _scan_generic(t, keywords={"and", "break", "do", "else", "elseif", "end", "false", "for", "function", "goto", "if", "in", "local", "nil", "not", "or", "repeat", "return", "then", "true", "until", "while"}, line_comment="--", string_delims=('"', "'")),
    "r": lambda t: _scan_generic(t, keywords={"if", "else", "repeat", "while", "function", "for", "in", "next", "break", "true", "false", "null", "NA", "Inf", "NaN"}, line_comment="#", string_delims=('"', "'")),
    "dockerfile": lambda t: _scan_generic(t, keywords={"FROM", "RUN", "CMD", "LABEL", "ENV", "ADD", "COPY", "ENTRYPOINT", "VOLUME", "USER", "WORKDIR", "ARG", "ONBUILD", "STOPSIGNAL", "HEALTHCHECK", "SHELL"}, line_comment="#", string_delims=('"', "'")),
    "text": tokenize_text,
}
