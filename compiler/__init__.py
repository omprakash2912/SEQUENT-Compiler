"""
SEQUENT Compiler Package - Phase 1 Prototype
A Temporal Event-Driven Domain-Specific Language and Compiler.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from compiler.tokens import Token, TokenType
from compiler.lexer import Lexer, LexerError
from compiler.ast import ProgramNode, format_ast
from compiler.parser import Parser, ParseError
from compiler.symbol_table import SymbolTable
from compiler.semantic_analyzer import SemanticAnalyzer, SemanticError
from compiler.temporal_analyzer import TemporalAnalyzer, TemporalError, TemporalConstraintRecord


@dataclass
class CompilationResult:
    """Encapsulates the complete result of compiling a SEQUENT source file."""
    tokens: List[Token] = field(default_factory=list)
    ast: Optional[ProgramNode] = None
    symbol_table: Optional[SymbolTable] = None
    temporal_constraints: List[TemporalConstraintRecord] = field(default_factory=list)
    success: bool = False
    error_category: Optional[str] = None
    error_message: Optional[str] = None


def compile_source(source: str) -> CompilationResult:
    """Executes the Phase 1 front-end compilation pipeline on the provided source code.

    Pipeline:
    Source -> Lexer -> Parser -> AST -> Semantic Analysis -> Temporal Analysis
    """
    result = CompilationResult()

    # 1. Lexical Analysis
    try:
        lexer = Lexer(source)
        result.tokens = lexer.tokenize()
    except LexerError as e:
        result.error_category = "LEXICAL ERROR"
        result.error_message = str(e)
        return result

    # 2. Syntax Analysis & AST Construction
    try:
        parser = Parser(result.tokens)
        result.ast = parser.parse()
    except ParseError as e:
        result.error_category = "SYNTAX ERROR"
        result.error_message = str(e)
        return result

    # 3. Semantic Analysis & Symbol Table Construction
    try:
        semantic_analyzer = SemanticAnalyzer()
        result.symbol_table = semantic_analyzer.analyze(result.ast)
    except SemanticError as e:
        result.error_category = "SEMANTIC ERROR"
        result.error_message = str(e)
        return result

    # 4. Temporal Constraint Analysis
    try:
        temporal_analyzer = TemporalAnalyzer()
        result.temporal_constraints = temporal_analyzer.analyze(result.ast, result.symbol_table)
    except TemporalError as e:
        result.error_category = "TEMPORAL ERROR"
        result.error_message = str(e)
        return result

    result.success = True
    return result
