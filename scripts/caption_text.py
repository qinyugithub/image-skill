#!/usr/bin/env python3
"""Normalize Chinese comic captions before layout."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable


WHITESPACE = re.compile(r"\s+")


def is_punctuation(character: str) -> bool:
    """Return whether a Unicode character is punctuation."""
    return bool(character) and unicodedata.category(character).startswith("P")


def caption_semantic_units(lines: Iterable[str]) -> list[str]:
    """Remove punctuation while keeping punctuation and input lines as semantic hints."""
    units: list[str] = []
    for raw_line in lines:
        current: list[str] = []
        for character in raw_line.strip():
            if is_punctuation(character):
                fragment = WHITESPACE.sub(" ", "".join(current)).strip()
                if fragment:
                    units.append(fragment)
                current = []
                continue
            current.append(character)
        fragment = WHITESPACE.sub(" ", "".join(current)).strip()
        if fragment:
            units.append(fragment)
    return units


def normalized_caption_text(lines: Iterable[str]) -> str:
    """Return punctuation-free caption text without fixed input line breaks."""
    return "".join(caption_semantic_units(lines))


def contains_punctuation(text: str) -> bool:
    return any(is_punctuation(character) for character in text)
