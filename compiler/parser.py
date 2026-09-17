"""
SEQUENT Compiler - Recursive-Descent Parser
Parses a stream of tokens into an Abstract Syntax Tree (AST).
"""

from typing import List, Optional
from compiler.tokens import Token, TokenType, TIME_UNITS
from compiler.ast import (
    ProgramNode,
    StateDeclNode,
    EventDeclNode,
    HandlerNode,
    AssignmentNode,
    ConstraintNode,
    DurationNode,
    LiteralNode,
)


class ParseError(Exception):
    """Exception raised for syntax errors during parsing."""

    def __init__(self, message: str, line: int, column: int):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"SYNTAX ERROR: {message} at line {line}, column {column}")


class Parser:
    """Hand-written recursive-descent parser for SEQUENT grammar."""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def _peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]  # Return EOF

    def _advance(self) -> Token:
        tok = self._peek()
        if tok.type != TokenType.EOF:
            self.pos += 1
        return tok

    def _consume(self, expected_type: TokenType, error_msg: Optional[str] = None) -> Token:
        tok = self._peek()
        if tok.type == expected_type:
            return self._advance()
        msg = error_msg or f"Expected '{expected_type.value}', found '{tok.value}'"
        raise ParseError(msg, tok.line, tok.column)

    def _parse_identifier(self, context: str = "identifier") -> Token:
        tok = self._peek()
        if tok.type in (TokenType.IDENTIFIER, TokenType.TIME_UNIT):
            return self._advance()
        raise ParseError(f"Expected {context}, found '{tok.value}'", tok.line, tok.column)

    def _parse_literal(self) -> LiteralNode:
        tok = self._peek()
        if tok.type == TokenType.INT:
            self._advance()
            return LiteralNode(value=tok.value, lit_type="int", line=tok.line, column=tok.column)
        if tok.type == TokenType.FLOAT:
            self._advance()
            return LiteralNode(value=tok.value, lit_type="float", line=tok.line, column=tok.column)
        if tok.type == TokenType.STRING:
            self._advance()
            return LiteralNode(value=tok.value, lit_type="string", line=tok.line, column=tok.column)
        if tok.type == TokenType.BOOL:
            self._advance()
            return LiteralNode(value=tok.value, lit_type="bool", line=tok.line, column=tok.column)

        raise ParseError(f"Expected literal value (int, float, string, or bool), found '{tok.value}'", tok.line, tok.column)

    def _parse_duration(self) -> DurationNode:
        amount_tok = self._consume(TokenType.INT, "Expected integer duration amount")
        unit_tok = self._peek()
        if unit_tok.type == TokenType.TIME_UNIT or (unit_tok.type == TokenType.IDENTIFIER and unit_tok.value in TIME_UNITS):
            self._advance()
            return DurationNode(
                amount=int(amount_tok.value),
                unit=str(unit_tok.value),
                line=amount_tok.line,
                column=amount_tok.column,
            )
        raise ParseError(f"Expected time unit ('ms', 's', 'm', 'h'), found '{unit_tok.value}'", unit_tok.line, unit_tok.column)

    def _parse_state_declaration(self) -> StateDeclNode:
        state_tok = self._consume(TokenType.STATE)
        ident_tok = self._parse_identifier("state identifier")
        self._consume(TokenType.EQUALS, f"Expected '=' after state identifier '{ident_tok.value}'")
        lit = self._parse_literal()
        return StateDeclNode(
            name=str(ident_tok.value),
            initial_value=lit,
            line=state_tok.line,
            column=state_tok.column,
        )

    def _parse_event_declaration(self) -> EventDeclNode:
        event_tok = self._consume(TokenType.EVENT)
        ident_tok = self._parse_identifier("event identifier")
        return EventDeclNode(
            name=str(ident_tok.value),
            line=event_tok.line,
            column=event_tok.column,
        )

    def _parse_assignment(self) -> AssignmentNode:
        ident_tok = self._parse_identifier("state identifier for assignment")
        self._consume(TokenType.EQUALS, f"Expected '=' after identifier '{ident_tok.value}'")
        lit = self._parse_literal()
        return AssignmentNode(
            state_name=str(ident_tok.value),
            value=lit,
            line=ident_tok.line,
            column=ident_tok.column,
        )

    def _parse_handler(self) -> HandlerNode:
        on_tok = self._consume(TokenType.ON)
        event_tok = self._parse_identifier("event identifier in handler")
        self._consume(TokenType.LBRACE, f"Expected '{{' to open handler for event '{event_tok.value}'")

        assignments: List[AssignmentNode] = []
        while self._peek().type in (TokenType.IDENTIFIER, TokenType.TIME_UNIT):
            assignments.append(self._parse_assignment())

        self._consume(TokenType.RBRACE, f"Expected '}}' to close handler for event '{event_tok.value}'")
        return HandlerNode(
            event_name=str(event_tok.value),
            assignments=assignments,
            line=on_tok.line,
            column=on_tok.column,
        )

    def _parse_constraint(self) -> ConstraintNode:
        c_tok = self._consume(TokenType.CONSTRAINT)
        source_tok = self._parse_identifier("source event in constraint")
        self._consume(TokenType.ARROW, f"Expected '->' after source event '{source_tok.value}'")
        target_tok = self._parse_identifier("target event in constraint")
        self._consume(TokenType.WITHIN, "Expected 'within' in temporal constraint")
        duration = self._parse_duration()
        return ConstraintNode(
            source_event=str(source_tok.value),
            target_event=str(target_tok.value),
            duration=duration,
            line=c_tok.line,
            column=c_tok.column,
        )

    def _parse_system_body(self, program: ProgramNode) -> None:
        while self._peek().type not in (TokenType.RBRACE, TokenType.EOF):
            tok = self._peek()
            if tok.type == TokenType.STATE:
                program.declarations.append(self._parse_state_declaration())
            elif tok.type == TokenType.EVENT:
                program.declarations.append(self._parse_event_declaration())
            elif tok.type == TokenType.ON:
                program.handlers.append(self._parse_handler())
            elif tok.type == TokenType.CONSTRAINT:
                program.constraints.append(self._parse_constraint())
            else:
                raise ParseError(f"Unexpected token '{tok.value}' in system body", tok.line, tok.column)

    def parse(self) -> ProgramNode:
        """Parses the token stream and returns the root ProgramNode AST."""
        sys_tok = self._consume(TokenType.SYSTEM, "Expected 'system' keyword at start of program")
        name_tok = self._parse_identifier("system name")
        self._consume(TokenType.LBRACE, f"Expected '{{' after system name '{name_tok.value}'")

        program = ProgramNode(
            system_name=str(name_tok.value),
            line=sys_tok.line,
            column=sys_tok.column,
        )
        self._parse_system_body(program)

        self._consume(TokenType.RBRACE, f"Expected '}}' to close system '{name_tok.value}'")

        if self._peek().type != TokenType.EOF:
            extra = self._peek()
            raise ParseError(f"Unexpected token '{extra.value}' after system definition", extra.line, extra.column)

        return program
