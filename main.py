"""
SEQUENT Compiler - Main Command-Line Interface Driver
Entrypoint for compiling SEQUENT DSL source files, inspecting compiler stages,
and running programs on the SEQUENT Virtual Machine.
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
from compiler.ir import IRGenerator, format_ir
from compiler.ir_optimizer import IROptimizer, format_optimization_comparison
from compiler.bytecode import BytecodeGenerator, format_bytecode
from compiler.runtime import (
    SequentRuntime,
    format_runtime_log,
)
from compiler import (
    parse_timeline_string,
    extract_timeline_from_source,
    compile_source,
    execute_source,
)


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


def compile_and_run_file(
    filepath: str,
    show_tokens: bool = False,
    show_ast: bool = False,
    show_symbols: bool = False,
    show_temporal: bool = False,
    show_ir: bool = False,
    show_optimize: bool = False,
    show_bytecode: bool = False,
    run_vm: bool = False,
    events_spec: str = "",
    json_output: bool = False,
) -> int:
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

    # Stage 4: Temporal Constraint Analysis (Static)
    try:
        temporal_analyzer = TemporalAnalyzer()
        temporal_constraints = temporal_analyzer.analyze(ast, symbol_table)
    except TemporalError as e:
        print(str(e), file=sys.stderr)
        print("COMPILATION FAILED", file=sys.stderr)
        return 1

    if show_temporal:
        print(temporal_analyzer.format_display())
        print()

    # Stage 5: Intermediate Representation (IR)
    ir_gen = IRGenerator()
    ir_prog = ir_gen.generate(ast, symbol_table)

    if show_ir:
        print(format_ir(ir_prog))
        print()

    # Stage 6: IR Optimization
    optimizer = IROptimizer()
    opt_ir_prog, opt_stats = optimizer.optimize(ir_prog)

    if show_optimize:
        print(format_optimization_comparison(ir_prog, opt_ir_prog, opt_stats))
        print()

    # Stage 7: Bytecode Generation
    target_ir = opt_ir_prog if show_optimize else ir_prog
    bc_gen = BytecodeGenerator()
    compiled_prog = bc_gen.generate(target_ir)

    if show_bytecode:
        print(format_bytecode(compiled_prog))
        print()

    # Stage 8: VM Execution & Runtime Monitoring
    if run_vm or json_output:
        # Determine event timeline
        if events_spec.strip():
            timeline = parse_timeline_string(events_spec)
        else:
            timeline = extract_timeline_from_source(source)
            if not timeline and compiled_prog.events:
                t = 0
                timeline = []
                for ev in compiled_prog.events:
                    timeline.append((ev, t))
                    t += 1000

        runtime = SequentRuntime(compiled_prog)
        exec_result = runtime.run_simulation(timeline)

        if json_output:
            print(exec_result.to_json(indent=2))
        else:
            print(format_runtime_log(exec_result))
            print()
        return 0 if exec_result.success else 2

    # Normal success summary when no specific display or run flag is requested
    if not (show_tokens or show_ast or show_symbols or show_temporal or show_ir or show_optimize or show_bytecode):
        print("LEXICAL ANALYSIS ✓")
        print("SYNTAX ANALYSIS ✓")
        print("AST CONSTRUCTION ✓")
        print("SYMBOL TABLE ✓")
        print("SEMANTIC ANALYSIS ✓")
        print("TEMPORAL ANALYSIS ✓")
        print("IR GENERATION ✓")
        print("BYTECODE GENERATION ✓")
        print("COMPILATION SUCCESSFUL")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="SEQUENT DSL Compiler & Virtual Machine - Phase 2 Core Implementation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "file",
        help="Path to the .seq source file to compile/run",
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
        help="Display static temporal constraints",
    )
    parser.add_argument(
        "--ir",
        action="store_true",
        help="Display generated Intermediate Representation (IR)",
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Run IR optimization and show before/after comparison",
    )
    parser.add_argument(
        "--bytecode",
        action="store_true",
        help="Display generated SEQUENT Virtual Machine bytecode",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute the program on the SEQUENT Virtual Machine",
    )
    parser.add_argument(
        "--events",
        type=str,
        default="",
        help="Custom event timeline specification (e.g., 'EmergencyDetected@0ms,TeamDispatched@3200ms')",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output runtime execution telemetry as structured JSON",
    )

    args = parser.parse_args()
    exit_code = compile_and_run_file(
        filepath=args.file,
        show_tokens=args.tokens,
        show_ast=args.ast,
        show_symbols=args.symbols,
        show_temporal=args.temporal,
        show_ir=args.ir,
        show_optimize=args.optimize,
        show_bytecode=args.bytecode,
        run_vm=args.run,
        events_spec=args.events,
        json_output=args.json,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()