"""
SEQUENT Compiler - Token Definitions
Defines the token types and Token data structure for the SEQUENT DSL.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TokenType(Enum):
    # Keywords
    SYSTEM = "SYSTEM"
    STATE = "STATE"
    EVENT = "EVENT"
    ON = "ON"
    CONSTRAINT = "CONSTRAINT"
    WITHIN = "WITHIN"

    # Literals
    INT = "INT"
    FLOAT = "FLOAT"
    STRING = "STRING"
    BOOL = "BOOL"

    # Identifiers
    IDENTIFIER = "IDENTIFIER"

    # Operators & Delimiters
    EQUALS = "="
    ARROW = "->"
    LBRACE = "{"
    RBRACE = "}"

    # Duration Units
    TIME_UNIT = "TIME_UNIT"

    # End of File & Unknown
    EOF = "EOF"
    UNKNOWN = "UNKNOWN"


KEYWORDS = {
    "system": TokenType.SYSTEM,
    "state": TokenType.STATE,
    "event": TokenType.EVENT,
    "on": TokenType.ON,
    "constraint": TokenType.CONSTRAINT,
    "within": TokenType.WITHIN,
    "true": TokenType.BOOL,
    "false": TokenType.BOOL,
}

TIME_UNITS = {"ms", "s", "m", "h"}


@dataclass
class Token:
    type: TokenType
    value: Any
    line: int
    column: int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, line={self.line}, col={self.column})"
