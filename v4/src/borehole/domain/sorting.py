"""Natural ordering for project identifiers."""

from __future__ import annotations

import re

_IDENTIFIER_PATTERN = re.compile(r"^([A-Za-z]+)(\d+)(?:-(\d+))?$")

NaturalIdentifierKey = tuple[int, str, int, int, int, str]
BoreholeSortKey = tuple[int, NaturalIdentifierKey]


def natural_identifier_key(value: str) -> NaturalIdentifierKey:
    match = _IDENTIFIER_PATTERN.fullmatch(value.strip())
    if match is None:
        return 1, "", 0, 0, 0, value.casefold()
    letters, main_number, sub_number = match.groups()
    return (
        0,
        letters.upper(),
        int(main_number),
        0 if sub_number is None else 1,
        int(sub_number or 0),
        value.casefold(),
    )


def borehole_sort_key(prefix: str) -> BoreholeSortKey:
    upper = prefix.upper()
    if upper.startswith("NZK"):
        type_order = 1
    elif upper.startswith("ZK"):
        type_order = 0
    else:
        type_order = 2
    return type_order, natural_identifier_key(prefix)


def profile_sort_key(name: str) -> NaturalIdentifierKey:
    return natural_identifier_key(name)
