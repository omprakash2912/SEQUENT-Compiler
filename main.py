"""
SEQUENT Compiler - Main Command-Line Interface Driver
Entrypoint for compiling SEQUENT DSL source files and inspecting compiler stages.
"""

import argparse
import sys
from pathlib import Path

# Ensure UTF-8 output encoding across platforms
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from compiler.tokens import Token
from compiler.lexer import Lexer, LexerError
from compiler.ast import format_ast
from compiler.parser import Parser, ParseError
from compiler.semantic_analyzer import SemanticAnalyzer, SemanticError
from compiler.temporal_analyzer import TemporalAnalyzer, TemporalError


def print_tokens(tokens):
    print("============================================================")
    print("                        TOKEN STREAM                        ")
    print("============================================================")
    print(f"  {'Type':<16} {'Value':<24} {'Location':<14}")
    print(f"  {'-'*16} {'-'*24} {'-'*14}")
    for tok in tokens:
        val_str = repr(tok.value) if tok.value != "" else "''"
        loc_str = f"Line {tok.line}, Col {tok.column}"
        print(f"  {tok.type.name:<16} {val_str:<24} {loc_str:<14}")
    print("============================================================\n")


def compile_file(filepath: str, show_tokens: bool = False, show_ast: bool = False,
                 show_symbols: bool = False, show_temporal: bool = False) -> int:
    path = Path(filepath)
    if not path.exists():
        print(f"ERROR: File '{filepath}' not found.", file=sys.stderr)
        return 1

    try:
        source = path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"ERROR: Could not read file '{filepath}': {e}", file=sys.stderr)
        return 1

    # Stage 1: Lexical Analysis
    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
    except LexerError as e:
        print(str(e), file=sys.stderr)
        print("COMPILATION FAILED", file=sys.stderr)
        return 1

    if show_tokens:
        print_tokens(tokens)

    # Stage 2: Syntax Analysis & AST Construction
    try:
        parser = Parser(tokens)
        ast = parser.parse()
    except ParseError as e:
        print(str(e), file=sys.stderr)
        print("COMPILATION FAILED", file=sys.stderr)
        return 1

    if show_ast:
        print("============================================================")
        print("                   ABSTRACT SYNTAX TREE                     ")
        print("============================================================")
        print(format_ast(ast))
        print("============================================================\n")

    # Stage 3: Semantic Analysis & Symbol Table Creation
    try:
        semantic_analyzer = SemanticAnalyzer()
        symbol_table = semantic_analyzer.analyze(ast)
    except SemanticError as e:
        print(str(e), file=sys.stderr)
        print("COMPILATION FAILED", file=sys.stderr)
        return 1

    if show_symbols:
        print(symbol_table.format_display())
        print()

    # Stage 4: Temporal Constraint Analysis
    try:
        temporal_analyzer = TemporalAnalyzer()
        temporal_analyzer.analyze(ast, symbol_table)
    except TemporalError as e:
        print(str(e), file=sys.stderr)
        print("COMPILATION FAILED", file=sys.stderr)
        return 1

    if show_temporal:
        print(temporal_analyzer.format_display())
        print()

    # Normal success summary
    print("LEXICAL ANALYSIS ✓")
    print("SYNTAX ANALYSIS ✓")
    print("AST CONSTRUCTION ✓")
    print("SYMBOL TABLE ✓")
    print("SEMANTIC ANALYSIS ✓")
    print("TEMPORAL ANALYSIS ✓")
    print("COMPILATION SUCCESSFUL")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="SEQUENT DSL Compiler - Phase 1 Initial Prototype",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "file",
        help="Path to the .seq source file to compile",
    )
    parser.add_argument(
        "--tokens",
        action="store_true",
        help="Display the token stream from lexical analysis",
    )
    parser.add_argument(
        "--ast",
        action="store_true",
        help="Display the pretty-printed Abstract Syntax Tree",
    )
    parser.add_argument(
        "--symbols",
        action="store_true",
        help="Display the populated Symbol Table",
    )
    parser.add_argument(
        "--temporal",
        action="store_true",
        help="Display the registered and normalized temporal constraints",
    )

    args = parser.parse_args()
    exit_code = compile_file(
        filepath=args.file,
        show_tokens=args.tokens,
        show_ast=args.ast,
        show_symbols=args.symbols,
        show_temporal=args.temporal,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
