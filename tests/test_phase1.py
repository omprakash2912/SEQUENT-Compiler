"""
SEQUENT Compiler - Phase 1 Test Suite
Deterministic unit and integration tests using Python's standard unittest.
"""

import unittest
from pathlib import Path

from compiler.tokens import Token, TokenType
from compiler.lexer import Lexer, LexerError
from compiler.parser import Parser, ParseError
from compiler.ast import (
    ProgramNode,
    StateDeclNode,
    EventDeclNode,
    HandlerNode,
    ConstraintNode,
    format_ast,
)
from compiler.symbol_table import SymbolTable
from compiler.semantic_analyzer import SemanticAnalyzer, SemanticError
from compiler.temporal_analyzer import TemporalAnalyzer, TemporalError
from compiler import compile_source


class TestLexer(unittest.TestCase):
    """Unit tests for Lexical Analysis."""

    def test_keywords(self):
        source = "system state event on constraint within true false"
        tokens = Lexer(source).tokenize()
        types = [t.type for t in tokens]
        expected = [
            TokenType.SYSTEM,
            TokenType.STATE,
            TokenType.EVENT,
            TokenType.ON,
            TokenType.CONSTRAINT,
            TokenType.WITHIN,
            TokenType.BOOL,
            TokenType.BOOL,
            TokenType.EOF,
        ]
        self.assertEqual(types, expected)

    def test_identifiers(self):
        source = "EmergencyResponse active team_status var123"
        tokens = Lexer(source).tokenize()
        types = [t.type for t in tokens]
        values = [t.value for t in tokens]
        self.assertEqual(types, [TokenType.IDENTIFIER] * 4 + [TokenType.EOF])
        self.assertEqual(values[:-1], ["EmergencyResponse", "active", "team_status", "var123"])

    def test_literals(self):
        source = '42 3.14 "hello world" "with\\nescape" true false'
        tokens = Lexer(source).tokenize()
        self.assertEqual(tokens[0].type, TokenType.INT)
        self.assertEqual(tokens[0].value, 42)
        self.assertEqual(tokens[1].type, TokenType.FLOAT)
        self.assertEqual(tokens[1].value, 3.14)
        self.assertEqual(tokens[2].type, TokenType.STRING)
        self.assertEqual(tokens[2].value, "hello world")
        self.assertEqual(tokens[3].type, TokenType.STRING)
        self.assertEqual(tokens[3].value, "with\nescape")
        self.assertEqual(tokens[4].type, TokenType.BOOL)
        self.assertEqual(tokens[4].value, True)
        self.assertEqual(tokens[5].type, TokenType.BOOL)
        self.assertEqual(tokens[5].value, False)

    def test_operators_and_symbols(self):
        source = "= -> { }"
        tokens = Lexer(source).tokenize()
        types = [t.type for t in tokens]
        self.assertEqual(types, [TokenType.EQUALS, TokenType.ARROW, TokenType.LBRACE, TokenType.RBRACE, TokenType.EOF])

    def test_duration_tokens(self):
        source = "5s 30m 100ms 2h"
        tokens = Lexer(source).tokenize()
        values = [(t.type, t.value) for t in tokens[:-1]]
        expected = [
            (TokenType.INT, 5),
            (TokenType.TIME_UNIT, "s"),
            (TokenType.INT, 30),
            (TokenType.TIME_UNIT, "m"),
            (TokenType.INT, 100),
            (TokenType.TIME_UNIT, "ms"),
            (TokenType.INT, 2),
            (TokenType.TIME_UNIT, "h"),
        ]
        self.assertEqual(values, expected)

    def test_comments_and_whitespace(self):
        source = """
        // Header comment
        system Test { // inline comment
            state x = 1
        }
        """
        tokens = Lexer(source).tokenize()
        types = [t.type for t in tokens]
        self.assertNotIn(TokenType.UNKNOWN, types)
        self.assertEqual(tokens[0].type, TokenType.SYSTEM)

    def test_line_and_column_tracking(self):
        source = "system\n  state a = 1"
        tokens = Lexer(source).tokenize()
        self.assertEqual(tokens[0].line, 1)
        self.assertEqual(tokens[0].column, 1)
        self.assertEqual(tokens[1].line, 2)
        self.assertEqual(tokens[1].column, 3)

    def test_lexer_error_invalid_char(self):
        source = "system Test { @ }"
        with self.assertRaises(LexerError) as ctx:
            Lexer(source).tokenize()
        self.assertIn("Unexpected character '@'", str(ctx.exception))

    def test_lexer_error_unterminated_string(self):
        source = 'system Test { state s = "unclosed }'
        with self.assertRaises(LexerError) as ctx:
            Lexer(source).tokenize()
        self.assertIn("Unterminated string literal", str(ctx.exception))


class TestParserAndAST(unittest.TestCase):
    """Unit tests for Parser and AST Construction."""

    def test_valid_parsing(self):
        source = """
        system TestSystem {
            state ready = true
            event Start
            on Start {
                ready = false
            }
            constraint Start -> Start within 10s
        }
        """
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()

        self.assertIsInstance(ast, ProgramNode)
        self.assertEqual(ast.system_name, "TestSystem")
        self.assertEqual(len(ast.declarations), 2)
        self.assertIsInstance(ast.declarations[0], StateDeclNode)
        self.assertEqual(ast.declarations[0].name, "ready")
        self.assertIsInstance(ast.declarations[1], EventDeclNode)
        self.assertEqual(ast.declarations[1].name, "Start")
        self.assertEqual(len(ast.handlers), 1)
        self.assertEqual(ast.handlers[0].event_name, "Start")
        self.assertEqual(len(ast.constraints), 1)
        self.assertEqual(ast.constraints[0].duration.amount, 10)
        self.assertEqual(ast.constraints[0].duration.unit, "s")

    def test_ast_pretty_print(self):
        source = """
        system Demo {
            state count = 0
            event Tick
        }
        """
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        formatted = format_ast(ast)
        self.assertIn("Program: Demo", formatted)
        self.assertIn("State: count = 0 [int]", formatted)
        self.assertIn("Event: Tick", formatted)

    def test_syntax_error_missing_closing_brace(self):
        source = "system Broken { state x = 1"
        tokens = Lexer(source).tokenize()
        with self.assertRaises(ParseError) as ctx:
            Parser(tokens).parse()
        self.assertIn("SYNTAX ERROR", str(ctx.exception))

    def test_syntax_error_missing_system_keyword(self):
        source = "Broken { }"
        tokens = Lexer(source).tokenize()
        with self.assertRaises(ParseError) as ctx:
            Parser(tokens).parse()
        self.assertIn("Expected 'system' keyword", str(ctx.exception))


class TestSymbolTable(unittest.TestCase):
    """Unit tests for Symbol Table operations."""

    def test_symbol_table_operations(self):
        table = SymbolTable()
        self.assertTrue(table.define_state("active", "bool", False, 1, 1))
        self.assertTrue(table.define_event("Alert", 2, 1))

        # Check lookup
        state = table.lookup_state("active")
        self.assertIsNotNone(state)
        self.assertEqual(state.inferred_type, "bool")
        self.assertEqual(state.initial_value, False)

        event = table.lookup_event("Alert")
        self.assertIsNotNone(event)
        self.assertEqual(event.name, "Alert")

        # Duplicate state or cross-type definition rejection
        self.assertFalse(table.define_state("active", "bool", True, 3, 1))
        self.assertFalse(table.define_event("active", 4, 1))
        self.assertFalse(table.define_state("Alert", "int", 0, 5, 1))

    def test_symbol_table_display(self):
        table = SymbolTable()
        table.define_state("flag", "bool", True, 1, 1)
        table.define_event("Ping", 2, 1)
        display = table.format_display()
        self.assertIn("flag", display)
        self.assertIn("bool", display)
        self.assertIn("Ping", display)


class TestSemanticAnalyzer(unittest.TestCase):
    """Unit tests for Semantic Analysis."""

    def _parse(self, source: str) -> ProgramNode:
        return Parser(Lexer(source).tokenize()).parse()

    def test_duplicate_state_declaration(self):
        source = """
        system DuplicateState {
            state active = false
            state active = true
        }
        """
        ast = self._parse(source)
        with self.assertRaises(SemanticError) as ctx:
            SemanticAnalyzer().analyze(ast)
        self.assertIn("Duplicate state declaration 'active'", str(ctx.exception))

    def test_duplicate_event_declaration(self):
        source = """
        system DuplicateEvent {
            event Triggered
            event Triggered
        }
        """
        ast = self._parse(source)
        with self.assertRaises(SemanticError) as ctx:
            SemanticAnalyzer().analyze(ast)
        self.assertIn("Duplicate event declaration 'Triggered'", str(ctx.exception))

    def test_undefined_state_assignment(self):
        source = """
        system UndefinedState {
            event Start
            on Start {
                unknownState = true
            }
        }
        """
        ast = self._parse(source)
        with self.assertRaises(SemanticError) as ctx:
            SemanticAnalyzer().analyze(ast)
        self.assertIn("Undefined state 'unknownState'", str(ctx.exception))

    def test_undefined_event_in_handler(self):
        source = """
        system UndefinedEventHandler {
            state active = false
            on GhostEvent {
                active = true
            }
        }
        """
        ast = self._parse(source)
        with self.assertRaises(SemanticError) as ctx:
            SemanticAnalyzer().analyze(ast)
        self.assertIn("Undefined event 'GhostEvent' in handler", str(ctx.exception))

    def test_type_mismatch_error(self):
        source = """
        system TypeMismatch {
            state active = false
            event Trigger
            on Trigger {
                active = "YES"
            }
        }
        """
        ast = self._parse(source)
        with self.assertRaises(SemanticError) as ctx:
            SemanticAnalyzer().analyze(ast)
        self.assertIn("Type mismatch for state 'active'. Expected bool but got string.", str(ctx.exception))


class TestTemporalAnalyzer(unittest.TestCase):
    """Unit tests for Temporal Constraint Analysis."""

    def _parse_and_analyze(self, source: str):
        ast = Parser(Lexer(source).tokenize()).parse()
        symbols = SemanticAnalyzer().analyze(ast)
        return ast, symbols

    def test_valid_temporal_normalization(self):
        source = """
        system Timing {
            event A
            event B
            event C
            event D
            constraint A -> B within 500ms
            constraint B -> C within 5s
            constraint C -> D within 2m
            constraint D -> A within 1h
        }
        """
        ast, symbols = self._parse_and_analyze(source)
        records = TemporalAnalyzer().analyze(ast, symbols)
        self.assertEqual(len(records), 4)
        self.assertEqual(records[0].duration_ms, 500)
        self.assertEqual(records[1].duration_ms, 5000)
        self.assertEqual(records[2].duration_ms, 120000)
        self.assertEqual(records[3].duration_ms, 3600000)

    def test_undefined_source_event(self):
        source = """
        system MissingSource {
            event B
            constraint Missing -> B within 5s
        }
        """
        ast, symbols = self._parse_and_analyze(source)
        with self.assertRaises(TemporalError) as ctx:
            TemporalAnalyzer().analyze(ast, symbols)
        self.assertIn("Undefined event 'Missing' in temporal constraint.", str(ctx.exception))

    def test_undefined_target_event(self):
        source = """
        system MissingTarget {
            event A
            constraint A -> Missing within 5s
        }
        """
        ast, symbols = self._parse_and_analyze(source)
        with self.assertRaises(TemporalError) as ctx:
            TemporalAnalyzer().analyze(ast, symbols)
        self.assertIn("Undefined event 'Missing' in temporal constraint.", str(ctx.exception))

    def test_non_positive_duration(self):
        source = """
        system BadDuration {
            event A
            event B
            constraint A -> B within 0s
        }
        """
        ast, symbols = self._parse_and_analyze(source)
        with self.assertRaises(TemporalError) as ctx:
            TemporalAnalyzer().analyze(ast, symbols)
        self.assertIn("Non-positive duration", str(ctx.exception))


class TestEndToEndExamples(unittest.TestCase):
    """Integration tests compiling the actual project example files."""

    def test_compile_valid_example(self):
        path = Path("examples/valid.seq")
        source = path.read_text(encoding="utf-8")
        result = compile_source(source)
        self.assertTrue(result.success)
        self.assertIsNone(result.error_category)
        self.assertEqual(len(result.symbol_table.states), 2)
        self.assertEqual(len(result.symbol_table.events), 3)
        self.assertEqual(len(result.temporal_constraints), 2)

    def test_compile_syntax_error_example(self):
        path = Path("examples/syntax_error.seq")
        source = path.read_text(encoding="utf-8")
        result = compile_source(source)
        self.assertFalse(result.success)
        self.assertEqual(result.error_category, "SYNTAX ERROR")

    def test_compile_semantic_error_example(self):
        path = Path("examples/semantic_error.seq")
        source = path.read_text(encoding="utf-8")
        result = compile_source(source)
        self.assertFalse(result.success)
        self.assertEqual(result.error_category, "SEMANTIC ERROR")
        self.assertIn("Undefined state 'unknownState'", result.error_message)

    def test_compile_temporal_error_example(self):
        path = Path("examples/temporal_error.seq")
        source = path.read_text(encoding="utf-8")
        result = compile_source(source)
        self.assertFalse(result.success)
        self.assertEqual(result.error_category, "TEMPORAL ERROR")
        self.assertIn("Undefined event 'UnknownEvent'", result.error_message)

    def test_compile_type_error_example(self):
        path = Path("examples/type_error.seq")
        source = path.read_text(encoding="utf-8")
        result = compile_source(source)
        self.assertFalse(result.success)
        self.assertEqual(result.error_category, "SEMANTIC ERROR")
        self.assertIn("Type mismatch for state 'active'", result.error_message)


if __name__ == "__main__":
    unittest.main()
