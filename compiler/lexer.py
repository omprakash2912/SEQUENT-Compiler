"""
SEQUENT Compiler - Lexical Analyzer
Scans SEQUENT DSL source code and produces a stream of tokens.
"""

from typing import List, Optional
from compiler.tokens import Token, TokenType, KEYWORDS, TIME_UNITS


class LexerError(Exception):
    """Exception raised for lexical errors during tokenization."""

    def __init__(self, message: str, line: int, column: int):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"LEXICAL ERROR: {message} at line {line}, column {column}")


class Lexer:
    """Hand-crafted lexical analyzer for SEQUENT DSL."""

    def __init__(self, source: str):
        self.source = source
        self.length = len(source)
        self.pos = 0
        self.line = 1
        self.column = 1

    def _peek(self, offset: int = 0) -> Optional[str]:
        idx = self.pos + offset
        if idx < self.length:
            return self.source[idx]
        return None

    def _advance(self) -> Optional[str]:
        if self.pos >= self.length:
            return None
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _skip_whitespace_and_comments(self) -> None:
        while self.pos < self.length:
            ch = self._peek()
            if ch in (" ", "\t", "\r", "\n"):
                self._advance()
            elif ch == "/" and self._peek(1) == "/":
                # Single-line comment: skip until newline or EOF
                self._advance()  # skip '/'
                self._advance()  # skip '/'
                while self.pos < self.length and self._peek() != "\n":
                    self._advance()
            else:
                break

    def _scan_string(self, start_line: int, start_col: int) -> Token:
        self._advance()  # consume opening quote
        chars: List[str] = []
        while self.pos < self.length:
            ch = self._peek()
            if ch == '"':
                self._advance()  # consume closing quote
                return Token(
                    type=TokenType.STRING,
                    value="".join(chars),
                    line=start_line,
                    column=start_col,
                )
            if ch == "\n" or ch is None:
                raise LexerError("Unterminated string literal", start_line, start_col)
            if ch == "\\":
                self._advance()
                esc = self._peek()
                if esc == "n":
                    chars.append("\n")
                elif esc == "t":
                    chars.append("\t")
                elif esc == '"':
                    chars.append('"')
                elif esc == "\\":
                    chars.append("\\")
                elif esc is None:
                    raise LexerError("Unterminated string literal escape", start_line, start_col)
                else:
                    chars.append(esc)
                self._advance()
            else:
                chars.append(ch)
                self._advance()

        raise LexerError("Unterminated string literal", start_line, start_col)

    def _scan_number(self, start_line: int, start_col: int) -> Token:
        num_chars: List[str] = []
        while self.pos < self.length and (self._peek() is not None and self._peek().isdigit()):
            num_chars.append(self._advance())

        is_float = False
        if self._peek() == "." and (self._peek(1) is not None and self._peek(1).isdigit()):
            is_float = True
            num_chars.append(self._advance())  # consume '.'
            while self.pos < self.length and (self._peek() is not None and self._peek().isdigit()):
                num_chars.append(self._advance())

        num_str = "".join(num_chars)
        if is_float:
            return Token(
                type=TokenType.FLOAT,
                value=float(num_str),
                line=start_line,
                column=start_col,
            )
        return Token(
            type=TokenType.INT,
            value=int(num_str),
            line=start_line,
            column=start_col,
        )

    def _scan_identifier_or_keyword(self, start_line: int, start_col: int) -> Token:
        ident_chars: List[str] = []
        while self.pos < self.length:
            ch = self._peek()
            if ch is not None and (ch.isalnum() or ch == "_"):
                ident_chars.append(self._advance())
            else:
                break

        ident_str = "".join(ident_chars)

        # Check for boolean literals
        if ident_str == "true":
            return Token(TokenType.BOOL, True, start_line, start_col)
        if ident_str == "false":
            return Token(TokenType.BOOL, False, start_line, start_col)

        # Check for keywords
        if ident_str in KEYWORDS:
            return Token(KEYWORDS[ident_str], ident_str, start_line, start_col)

        # Check for duration units (ms, s, m, h)
        if ident_str in TIME_UNITS:
            return Token(TokenType.TIME_UNIT, ident_str, start_line, start_col)

        # Otherwise standard identifier
        return Token(TokenType.IDENTIFIER, ident_str, start_line, start_col)

    def tokenize(self) -> List[Token]:
        """Tokenizes the entire source string into a list of Tokens ending with EOF."""
        tokens: List[Token] = []

        while True:
            self._skip_whitespace_and_comments()
            if self.pos >= self.length:
                tokens.append(Token(TokenType.EOF, "", self.line, self.column))
                break

            start_line = self.line
            start_col = self.column
            ch = self._peek()

            # Two-character operator: '->'
            if ch == "-" and self._peek(1) == ">":
                self._advance()
                self._advance()
                tokens.append(Token(TokenType.ARROW, "->", start_line, start_col))
                continue

            # Single-character operators & delimiters
            if ch == "=":
                self._advance()
                tokens.append(Token(TokenType.EQUALS, "=", start_line, start_col))
                continue

            if ch == "{":
                self._advance()
                tokens.append(Token(TokenType.LBRACE, "{", start_line, start_col))
                continue

            if ch == "}":
                self._advance()
                tokens.append(Token(TokenType.RBRACE, "}", start_line, start_col))
                continue

            # Strings
            if ch == '"':
                tokens.append(self._scan_string(start_line, start_col))
                continue

            # Numbers
            if ch.isdigit():
                tokens.append(self._scan_number(start_line, start_col))
                continue

            # Identifiers, keywords, booleans, and time units
            if ch.isalpha() or ch == "_":
                tokens.append(self._scan_identifier_or_keyword(start_line, start_col))
                continue

            # Unknown character
            bad_ch = self._advance()
            raise LexerError(f"Unexpected character '{bad_ch}'", start_line, start_col)

        return tokens
