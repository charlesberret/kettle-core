"""Load a versioned rubric and hash its normalised body.

Front matter carries ``version`` and, optionally, ``dimensions``. The hash is
SHA-256 over the body only, after normalisation, so a wording change invalidates
old scores and a version bump that leaves the body alone does not.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .yamlio import YAMLError, loads

_DIMENSION = re.compile(r"^[a-z][a-z0-9_]*$")


class RubricError(ValueError):
    pass


@dataclass(frozen=True)
class Rubric:
    path: Path
    version: str
    dimensions: tuple[str, ...]
    body: str
    sha256: str


def load_rubric(path: Path | str) -> Rubric:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RubricError(f"cannot read rubric {path}: {exc}") from exc
    front, body = split_front_matter(text)
    try:
        meta = loads(front) or {}
    except YAMLError as exc:
        raise RubricError(f"{path}: {exc}") from exc
    if not isinstance(meta, dict):
        raise RubricError(f"{path}: front matter must be a mapping")
    if "version" not in meta or meta["version"] is None:
        raise RubricError(f"{path}: front matter needs version")
    version = meta["version"]
    if isinstance(version, bool) or not isinstance(version, (str, int)):
        raise RubricError(f"{path}: version must be a string or integer")
    version_s = str(version)
    if not version_s.strip():
        raise RubricError(f"{path}: version is empty")
    raw_dims = meta.get("dimensions") or []
    if not isinstance(raw_dims, list) or not all(isinstance(d, str) for d in raw_dims):
        raise RubricError(f"{path}: dimensions must be a list of strings")
    dimensions: list[str] = []
    for dim in raw_dims:
        if not _DIMENSION.fullmatch(dim):
            raise RubricError(f"{path}: dimension {dim!r} is not a lowercase id")
        if dim in dimensions:
            raise RubricError(f"{path}: duplicate dimension {dim}")
        dimensions.append(dim)
    normalised = normalise_body(body)
    digest = hashlib.sha256(normalised.encode("utf-8")).hexdigest()
    return Rubric(
        path=path.resolve(),
        version=version_s,
        dimensions=tuple(dimensions),
        body=normalised,
        sha256=digest,
    )


def split_front_matter(text: str) -> tuple[str, str]:
    """Return ``(front matter, body)``. The body excludes both fences."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("\ufeff"):
        text = text[1:]
    if not text.startswith("---\n"):
        raise RubricError("rubric must open with a --- front-matter fence")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise RubricError("rubric front matter is not closed with ---")
    return text[4:end], text[end + 5 :]


def normalise_body(body: str) -> str:
    """Newlines to ``\\n``, strip trailing whitespace, drop surrounding blank lines.

    The hashed text ends with exactly one newline when it is non-empty. Internal
    blank lines stay, so a paragraph break changes the hash.
    """
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip(" \t") for line in body.split("\n")]
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return ""
    return "\n".join(lines) + "\n"
