"""
SEQUENT Compiler Package - Phase 2 Core Implementation
A Temporal Event-Driven Domain-Specific Language and Compiler.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

from compiler.tokens import Token, TokenType
from compiler.lexer import Lexer, LexerError
from compiler.ast import ProgramNode, format_ast
from compiler.parser import Parser, ParseError
from compiler.symbol_table import SymbolTable
from compiler.semantic_analyzer import SemanticAnalyzer, SemanticError
from compiler.temporal_analyzer import TemporalAnalyzer, TemporalError, TemporalConstraintRecord
from compiler.ir import IRProgram, IRGenerator, format_ir
from compiler.ir_optimizer import IROptimizer, OptimizationStats, format_optimization_comparison
from compiler.bytecode import CompiledProgram, BytecodeGenerator, format_bytecode
from compiler.vm import VirtualMachine, VMError
from compiler.runtime import (
    SequentRuntime,
    RuntimeExecutionResult,
    TemporalCheckRecord,
    format_runtime_log,
)


@dataclass
class CompilationResult:
    """Encapsulates the complete result of compiling a SEQUENT source file."""
    tokens: List[Token] = field(default_factory=list)
    ast: Optional[ProgramNode] = None
    symbol_table: Optional[SymbolTable] = None
    temporal_constraints: List[TemporalConstraintRecord] = field(default_factory=list)
    ir: Optional[IRProgram] = None
    optimized_ir: Optional[IRProgram] = None
    optimization_stats: Optional[OptimizationStats] = None
    bytecode: Optional[CompiledProgram] = None
    success: bool = False
    error_category: Optional[str] = None
    error_message: Optional[str] = None


def parse_timeline_string(timeline_str: str) -> List[Tuple[str, int]]:
    """Parses a timeline specification string such as:

    "EmergencyDetected@0ms, TeamDispatched@3200ms, IncidentResolved@5s"
    into a list of tuples: [("EmergencyDetected", 0), ("TeamDispatched", 3200), ("IncidentResolved", 5000)]
    """
    events: List[Tuple[str, int]] = []
    unit_multipliers = {"ms": 1, "s": 1000, "m": 60000, "h": 3600000}

    for item in timeline_str.split(","):
        item = item.strip()
        if not item:
            continue
        if "@" in item:
            name, time_part = item.split("@", 1)
            name = name.strip()
            time_part = time_part.strip().lower()

            match = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*(ms|s|m|h)?$", time_part)
            if match:
                val = float(match.group(1))
                unit = match.group(2) or "ms"
                mult = unit_multipliers.get(unit, 1)
                ts_ms = int(val * mult)
            else:
                try:
                    ts_ms = int(time_part)
                except ValueError:
                    ts_ms = 0
            events.append((name, ts_ms))
        else:
            events.append((item, 0))

    return events


def extract_timeline_from_source(source: str) -> List[Tuple[str, int]]:
    """Inspects source text for embedded timeline comments such as:

    // EVENTS: EmergencyDetected@0ms, TeamDispatched@3200ms
    """
    for line in source.splitlines():
        line_clean = line.strip()
        if line_clean.startswith("//") and "EVENTS:" in line_clean.upper():
            idx = line_clean.upper().index("EVENTS:") + len("EVENTS:")
            spec = line_clean[idx:].strip()
            return parse_timeline_string(spec)
    return []


def compile_source(source: str, optimize: bool = False) -> CompilationResult:
    """Executes the complete SEQUENT compilation pipeline.

    Pipeline:
    Source -> Lexer -> Parser -> AST -> Semantic Analysis -> Temporal Analysis
           -> IR Generation -> [IR Optimization] -> Bytecode Generation
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

    # 4. Temporal Constraint Analysis (Static)
    try:
        temporal_analyzer = TemporalAnalyzer()
        result.temporal_constraints = temporal_analyzer.analyze(result.ast, result.symbol_table)
    except TemporalError as e:
        result.error_category = "TEMPORAL ERROR"
        result.error_message = str(e)
        return result

    # 5. Intermediate Representation (IR) Generation
    ir_gen = IRGenerator()
    result.ir = ir_gen.generate(result.ast, result.symbol_table)

    # 6. IR Optimization (Optional or on request)
    optimizer = IROptimizer()
    opt_ir, stats = optimizer.optimize(result.ir)
    result.optimized_ir = opt_ir
    result.optimization_stats = stats

    target_ir = result.optimized_ir if optimize else result.ir

    # 7. Bytecode Generation
    bc_gen = BytecodeGenerator()
    result.bytecode = bc_gen.generate(target_ir)

    result.success = True
    return result


def execute_source(
    source: str,
    event_timeline: Optional[List[Tuple[str, int]]] = None,
    optimize: bool = False,
) -> Tuple[CompilationResult, Optional[RuntimeExecutionResult]]:
    """Compiles and executes a SEQUENT source program on the SEQUENT Virtual Machine."""
    c_res = compile_source(source, optimize=optimize)
    if not c_res.success or c_res.bytecode is None:
        return c_res, None

    # Resolve event timeline
    timeline = event_timeline
    if timeline is None:
        timeline = extract_timeline_from_source(source)
    if not timeline and c_res.bytecode.events:
        # Default scenario: trigger declared events with staggered timestamps
        t = 0
        timeline = []
        for ev in c_res.bytecode.events:
            timeline.append((ev, t))
            t += 1000

    runtime = SequentRuntime(c_res.bytecode)
    exec_res = runtime.run_simulation(timeline)
    return c_res, exec_res