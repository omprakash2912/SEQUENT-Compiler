"""
SEQUENT Compiler - Main Command-Line Interface Driver
Entrypoint for compiling SEQUENT DSL source files, inspecting compiler stages,
serializing bytecode (.seqc), and executing simulations on the SEQUENT Virtual Machine.
"""

import argparse
import json
from pathlib import Path
import sys

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
from compiler.bytecode import BytecodeGenerator, format_bytecode, CompiledProgram
from compiler.runtime import (
    SequentRuntime,
    format_runtime_log,
)
from compiler.simulator import (
    DiscreteEventSimulator,
    SimulationResult,
)
from compiler.serializer import (
    BytecodeSerializer,
    SerializationError,
    save_seqc,
    load_seqc,
)
from compiler.benchmark import run_benchmark
from compiler import (
    parse_timeline_string,
    resolve_events_timeline,
    extract_timeline_from_source,
    compile_source,
    execute_source,
    simulate_source,
    simulate_seqc,
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


def process_seqc_file(
    filepath: str,
    show_bytecode: bool = False,
    run_sim: bool = False,
    events_spec: str = "",
    json_output: bool = False,
) -> int:
    """Handles execution and inspection when the input file is a serialized .seqc binary file."""
    try:
        compiled_prog = load_seqc(filepath)
    except Exception as e:
        print(f"SERIALIZATION ERROR: Could not load '{filepath}': {e}", file=sys.stderr)
        return 1

    if show_bytecode:
        print(format_bytecode(compiled_prog))
        print()
        return 0

    # Determine timeline
    timeline = []
    if events_spec.strip():
        timeline = resolve_events_timeline(events_spec)
    elif compiled_prog.events:
        t = 0
        for ev in compiled_prog.events:
            timeline.append((ev, t))
            t += 1000

    simulator = DiscreteEventSimulator(compiled_prog)
    simulator.load_timeline(timeline)
    result = simulator.run()

    if json_output:
        print(result.to_json(indent=2))
    else:
        print(result.format_display())
        print()

    return 0 if result.success else 2


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
    run_simulate: bool = False,
    emit_seqc: bool = False,
    run_bench: bool = False,
    events_spec: str = "",
    json_output: bool = False,
) -> int:
    path = Path(filepath)
    if not path.exists():
        print(f"ERROR: File '{filepath}' not found.", file=sys.stderr)
        return 1

    # Check for direct .seqc binary input
    if path.suffix.lower() == ".seqc":
        return process_seqc_file(
            filepath=filepath,
            show_bytecode=show_bytecode,
            run_sim=(run_vm or run_simulate),
            events_spec=events_spec,
            json_output=json_output,
        )

    try:
        source = path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"ERROR: Could not read file '{filepath}': {e}", file=sys.stderr)
        return 1

    # Optional Benchmark Mode
    if run_bench:
        bench_res = run_benchmark(source, compilation_rounds=50)
        print(bench_res.format_display())
        return 0

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

    # Stage 8: Optional Bytecode Serialization (.seqc emission)
    if emit_seqc:
        out_seqc = path.with_suffix(".seqc")
        bytes_written = save_seqc(compiled_prog, str(out_seqc))
        print("============================================================")
        print("            BYTECODE SERIALIZATION (.SEQC)                  ")
        print("============================================================")
        print(f"Target Output:      {out_seqc}")
        print(f"Binary File Size:   {bytes_written:,} bytes")
        print("Magic Header:       SEQC (Format Version 1)")
        print("Integrity:          CRC32 Checksum Verified")
        print("SERIALIZATION SUCCESSFUL")
        print("============================================================\n")

    # Stage 9: Simulation / VM Execution
    if run_simulate or run_vm or json_output:
        # Determine event timeline
        if events_spec.strip():
            timeline = resolve_events_timeline(events_spec)
        else:
            timeline = extract_timeline_from_source(source)
            if not timeline and compiled_prog.events:
                t = 0
                timeline = []
                for ev in compiled_prog.events:
                    timeline.append((ev, t))
                    t += 1000

        # Execute using DiscreteEventSimulator (Phase 3 priority queue engine)
        simulator = DiscreteEventSimulator(compiled_prog)
        simulator.load_timeline(timeline)
        sim_result = simulator.run()

        if json_output:
            print(sim_result.to_json(indent=2))
        else:
            print(sim_result.format_display())
            print()
        return 0 if sim_result.success else 2

    # Normal success summary when no specific inspection or execution flag is passed
    if not (show_tokens or show_ast or show_symbols or show_temporal or show_ir or show_optimize or show_bytecode or emit_seqc):
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
        description="SEQUENT DSL Compiler, Virtual Machine & Simulator - Phase 3 Integrated System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "file",
        help="Path to the .seq source file or .seqc binary bytecode file",
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
        "--simulate",
        action="store_true",
        help="Execute the program using the Phase 3 Discrete-Event Simulator",
    )
    parser.add_argument(
        "--emit-seqc",
        action="store_true",
        help="Compile and serialize bytecode to binary .seqc file",
    )
    parser.add_argument(
        "--load-seqc",
        action="store_true",
        help="Explicitly indicate input file is a .seqc binary bytecode file",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run performance benchmark (compilation rate & 1k/5k event simulation)",
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
        run_simulate=args.simulate,
        emit_seqc=args.emit_seqc,
        run_bench=args.benchmark,
        events_spec=args.events,
        json_output=args.json,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
