#!/usr/bin/env python3
"""
SEQUENT Compiler - Web IDE & Execution Dashboard Server
Provides a zero-dependency local HTTP server using the Python standard library
to serve the IDE frontend and expose real SEQUENT compiler pipeline endpoints.
"""

import argparse
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import struct
import sys
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse
import zlib

# Ensure compiler package can be imported
WORKSPACE_ROOT = Path(__file__).resolve().parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from compiler.tokens import Token, TokenType
from compiler.lexer import Lexer, LexerError
from compiler.ast import (
    ASTNode,
    ProgramNode,
    StateDeclNode,
    EventDeclNode,
    HandlerNode,
    AssignmentNode,
    ConstraintNode,
    format_ast,
)
from compiler.parser import Parser, ParseError
from compiler.symbol_table import SymbolTable
from compiler.semantic_analyzer import SemanticAnalyzer, SemanticError
from compiler.temporal_analyzer import TemporalAnalyzer, TemporalError
from compiler.ir import IRGenerator, format_ir
from compiler.ir_optimizer import IROptimizer, format_optimization_comparison
from compiler.bytecode import BytecodeGenerator, format_bytecode, CompiledProgram
from compiler.simulator import DiscreteEventSimulator, SimulationResult
from compiler.serializer import (
    BytecodeSerializer,
    SerializationError,
    HEADER_STRUCT,
    HEADER_SIZE,
    SEQC_MAGIC,
    SEQC_VERSION,
)
from compiler import (
    parse_timeline_string,
    resolve_events_timeline,
    extract_timeline_from_source,
)
from compiler.diagnostics import (
    CompilerDiagnostic,
    create_diagnostic_from_error,
    calculate_column_span,
    TEMPLATES,
)


def ast_to_dict(node: Any) -> Dict[str, Any]:
    """Converts AST nodes into JSON-serializable dictionaries for visual tree rendering."""
    if isinstance(node, ProgramNode):
        return {
            "type": "Program",
            "system_name": node.system_name,
            "line": node.line,
            "column": node.column,
            "declarations": [ast_to_dict(d) for d in node.declarations],
            "handlers": [ast_to_dict(h) for h in node.handlers],
            "constraints": [ast_to_dict(c) for c in node.constraints],
        }
    elif isinstance(node, StateDeclNode):
        return {
            "type": "StateDecl",
            "name": node.name,
            "initial_value": node.initial_value.value,
            "lit_type": node.initial_value.lit_type,
            "line": node.line,
            "column": node.column,
        }
    elif isinstance(node, EventDeclNode):
        return {
            "type": "EventDecl",
            "name": node.name,
            "line": node.line,
            "column": node.column,
        }
    elif isinstance(node, HandlerNode):
        return {
            "type": "Handler",
            "event_name": node.event_name,
            "line": node.line,
            "column": node.column,
            "assignments": [ast_to_dict(a) for a in node.assignments],
        }
    elif isinstance(node, AssignmentNode):
        return {
            "type": "Assignment",
            "state_name": node.state_name,
            "value": node.value.value,
            "lit_type": node.value.lit_type,
            "line": node.line,
            "column": node.column,
        }
    elif isinstance(node, ConstraintNode):
        dur_str = f"{node.duration.amount}{node.duration.unit}"
        return {
            "type": "Constraint",
            "source_event": node.source_event,
            "target_event": node.target_event,
            "duration": dur_str,
            "raw_duration": dur_str,
            "amount": node.duration.amount,
            "unit": node.duration.unit,
            "line": node.line,
            "column": node.column,
        }
    return {"type": type(node).__name__}


def compile_for_ide(source: str, optimize: bool = False) -> Dict[str, Any]:
    """Executes all compiler stages and collects detailed structured telemetry."""
    stages_status = {
        "lexer": "not_executed",
        "parser": "not_executed",
        "symbols": "not_executed",
        "semantic": "not_executed",
        "temporal": "not_executed",
        "ir": "not_executed",
        "optimization": "not_executed",
        "bytecode": "not_executed",
    }
    partial_stages: Dict[str, Any] = {}

    # Stage 1: Lexical Analysis
    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        stages_status["lexer"] = "ok"
        tokens_data = [
            {
                "line": tok.line,
                "column": tok.column,
                "type": tok.type.name,
                "lexeme": tok.value if tok.value != "" else tok.type.name,
                "value": tok.value,
            }
            for tok in tokens
        ]
        partial_stages["tokens"] = tokens_data
    except LexerError as e:
        stages_status["lexer"] = "failed"
        diag = create_diagnostic_from_error(
            stage="LEXER",
            error_message=e.message,
            line=e.line,
            column=e.column,
            source_code=source,
            category="ERROR",
        )
        return {
            "success": False,
            "error": {
                "stage": "LEXER",
                "category": "LEXICAL ERROR",
                "message": e.message,
                "line": e.line,
                "column": e.column,
            },
            "stages_status": stages_status,
            "partial_stages": partial_stages,
            "diagnostics": [diag.to_dict()],
        }

    # Stage 2: Syntax Analysis & AST Construction
    try:
        parser = Parser(tokens)
        ast = parser.parse()
        stages_status["parser"] = "ok"
        partial_stages["ast"] = {
            "formatted": format_ast(ast),
            "tree": ast_to_dict(ast),
        }
        partial_stages["system_name"] = ast.system_name
    except ParseError as e:
        stages_status["parser"] = "failed"
        diag = create_diagnostic_from_error(
            stage="PARSER",
            error_message=e.message,
            line=e.line,
            column=e.column,
            source_code=source,
            category="ERROR",
        )
        return {
            "success": False,
            "error": {
                "stage": "PARSER",
                "category": "SYNTAX ERROR",
                "message": e.message,
                "line": e.line,
                "column": e.column,
            },
            "stages_status": stages_status,
            "partial_stages": partial_stages,
            "diagnostics": [diag.to_dict()],
        }

    # Stage 3: Semantic Analysis & Symbol Table Creation
    try:
        semantic_analyzer = SemanticAnalyzer()
        symbol_table = semantic_analyzer.analyze(ast)
        stages_status["symbols"] = "ok"

        # Inspect if any constraint references undeclared event identifiers
        unresolved_events = []
        for c in ast.constraints:
            if not symbol_table.has_event(c.source_event) and c.source_event not in unresolved_events:
                unresolved_events.append(c.source_event)
            if not symbol_table.has_event(c.target_event) and c.target_event not in unresolved_events:
                unresolved_events.append(c.target_event)

        symbols_data = {
            "states": [
                {
                    "name": s.name,
                    "type": s.inferred_type,
                    "initial_value": s.initial_value,
                    "line": s.line,
                    "column": s.column,
                }
                for s in symbol_table.states.values()
            ],
            "events": [
                {
                    "name": e.name,
                    "line": e.line,
                    "column": e.column,
                }
                for e in symbol_table.events.values()
            ],
            "formatted": symbol_table.format_display(),
        }
        partial_stages["symbols"] = symbols_data

        if unresolved_events:
            stages_status["semantic"] = "warning"
            partial_stages["semantic"] = {
                "status": "UNRESOLVED_IDENTIFIERS",
                "message": f"Declarations registered, but constraint references undeclared event(s): {', '.join(repr(ev) for ev in unresolved_events)}. Flagged for Temporal Analysis.",
                "unresolved_events": unresolved_events,
            }
        else:
            stages_status["semantic"] = "ok"
            partial_stages["semantic"] = {
                "status": "VALID",
                "message": "Semantic analysis passed successfully. All identifiers resolved and types verified.",
            }
    except SemanticError as e:
        stages_status["semantic"] = "failed"
        diag = create_diagnostic_from_error(
            stage="SEMANTIC",
            error_message=e.message,
            line=e.line,
            column=e.column,
            source_code=source,
            symbol_table=getattr(semantic_analyzer, "symbol_table", None),
            ast=ast,
            category="ERROR",
        )
        return {
            "success": False,
            "error": {
                "stage": "SEMANTIC",
                "category": "SEMANTIC ERROR",
                "message": e.message,
                "line": e.line,
                "column": e.column,
            },
            "stages_status": stages_status,
            "partial_stages": partial_stages,
            "diagnostics": [diag.to_dict()],
        }

    # Stage 4: Temporal Constraint Analysis (Static)
    try:
        temporal_analyzer = TemporalAnalyzer()
        temporal_constraints = temporal_analyzer.analyze(ast, symbol_table)
        stages_status["temporal"] = "ok"
        temporal_data = [
            {
                "source": c.source_event,
                "target": c.target_event,
                "raw_duration": c.raw_duration,
                "duration_ms": c.duration_ms,
                "line": c.line,
                "column": c.column,
                "status": "VALID",
            }
            for c in temporal_constraints
        ]
        partial_stages["temporal"] = {
            "constraints": temporal_data,
            "formatted": temporal_analyzer.format_display(),
            "status": "VALID",
        }
    except TemporalError as e:
        stages_status["temporal"] = "failed"
        temporal_data = []
        unit_multipliers = {"ms": 1, "s": 1000, "m": 60000, "h": 3600000}
        for c in ast.constraints:
            src_ok = symbol_table.has_event(c.source_event)
            tgt_ok = symbol_table.has_event(c.target_event)
            dur_str = f"{c.duration.amount}{c.duration.unit}"
            mult = unit_multipliers.get(c.duration.unit, 1)
            dur_ms = c.duration.amount * mult
            if not src_ok:
                c_status = f"UNDEFINED: '{c.source_event}'"
            elif not tgt_ok:
                c_status = f"UNDEFINED: '{c.target_event}'"
            elif c.duration.amount <= 0:
                c_status = "INVALID DURATION"
            else:
                c_status = "VALID"
            temporal_data.append({
                "source": c.source_event,
                "target": c.target_event,
                "raw_duration": dur_str,
                "duration_ms": dur_ms,
                "line": c.line,
                "column": c.column,
                "status": c_status,
            })
        partial_stages["temporal"] = {
            "constraints": temporal_data,
            "error": e.message,
            "status": "FAILED",
        }
        diag = create_diagnostic_from_error(
            stage="TEMPORAL",
            error_message=e.message,
            line=e.line,
            column=e.column,
            source_code=source,
            symbol_table=symbol_table,
            ast=ast,
            category="ERROR",
        )
        diagnostics_list = [diag.to_dict()]
        if unresolved_events and ast.constraints:
            c_first = ast.constraints[0]
            col, end_col, _, _ = calculate_column_span(source, c_first.line, c_first.column)
            warn_diag = CompilerDiagnostic(
                stage="SEMANTIC",
                severity="WARNING",
                line=c_first.line,
                column=col,
                end_column=end_col,
                message=f"Declarations registered, but constraint references undeclared event(s): {', '.join(repr(ev) for ev in unresolved_events)}.",
                explanation="One or more temporal constraints reference events that have not been declared.",
                suggestion=f"Declare missing events before static temporal validation.",
            )
            diagnostics_list.append(warn_diag.to_dict())

        return {
            "success": False,
            "error": {
                "stage": "TEMPORAL",
                "category": "TEMPORAL ERROR",
                "message": e.message,
                "line": e.line,
                "column": e.column,
            },
            "stages_status": stages_status,
            "partial_stages": partial_stages,
            "diagnostics": diagnostics_list,
        }

    # Stage 5: Intermediate Representation (IR) Generation
    ir_gen = IRGenerator()
    ir_prog = ir_gen.generate(ast, symbol_table)
    stages_status["ir"] = "ok"
    ir_instructions = [
        {
            "opcode": instr.opcode.name,
            "arg1": str(instr.arg1) if instr.arg1 is not None else None,
            "arg2": repr(instr.arg2) if instr.arg2 is not None else None,
            "arg3": str(instr.arg3) if instr.arg3 is not None else None,
            "source_line": instr.source_line,
            "comment": instr.comment,
        }
        for instr in ir_prog.instructions
    ]
    partial_stages["ir"] = {
        "instructions": ir_instructions,
        "formatted": format_ir(ir_prog),
    }

    # Stage 6: IR Optimization
    optimizer = IROptimizer()
    opt_ir_prog, opt_stats = optimizer.optimize(ir_prog)
    stages_status["optimization"] = "ok"
    opt_instructions = [
        {
            "opcode": instr.opcode.name,
            "arg1": str(instr.arg1) if instr.arg1 is not None else None,
            "arg2": repr(instr.arg2) if instr.arg2 is not None else None,
            "arg3": str(instr.arg3) if instr.arg3 is not None else None,
            "source_line": instr.source_line,
            "comment": instr.comment,
        }
        for instr in opt_ir_prog.instructions
    ]
    partial_stages["optimization"] = {
        "stats": {
            "initial_instructions": opt_stats.initial_instructions,
            "final_instructions": opt_stats.final_instructions,
            "instructions_eliminated": opt_stats.instructions_eliminated,
            "reduction_percentage": opt_stats.percentage_reduction,
            "passes": opt_stats.passes_run,
        },
        "instructions": opt_instructions,
        "formatted": format_optimization_comparison(ir_prog, opt_ir_prog, opt_stats),
    }

    # Stage 7: Bytecode Generation
    target_ir = opt_ir_prog if optimize else ir_prog
    bc_gen = BytecodeGenerator()
    compiled_prog = bc_gen.generate(target_ir)
    stages_status["bytecode"] = "ok"
    bc_instructions = [
        {
            "offset": instr.offset,
            "opcode": instr.opcode.name,
            "arg": repr(instr.arg) if instr.arg is not None else None,
            "source_line": instr.source_line,
            "comment": instr.comment,
        }
        for instr in compiled_prog.instructions
    ]
    partial_stages["bytecode"] = {
        "instructions": bc_instructions,
        "formatted": format_bytecode(compiled_prog),
        "total_instructions": len(compiled_prog.instructions),
        "handler_table": compiled_prog.handler_table,
    }

    return {
        "success": True,
        "system_name": ast.system_name,
        "stages_status": stages_status,
        "tokens": partial_stages["tokens"],
        "ast": partial_stages["ast"],
        "symbols": partial_stages["symbols"],
        "semantic": partial_stages["semantic"],
        "temporal": partial_stages["temporal"],
        "ir": partial_stages["ir"],
        "optimization": partial_stages["optimization"],
        "bytecode": partial_stages["bytecode"],
        "diagnostics": [],
        "_compiled_prog": compiled_prog,
    }


def simulate_for_ide(
    source_or_compiled: Any,
    events_spec: str = "",
    optimize: bool = False,
) -> Dict[str, Any]:
    """Compiles (if source) and executes program via DiscreteEventSimulator."""
    if isinstance(source_or_compiled, str):
        comp_res = compile_for_ide(source_or_compiled, optimize=optimize)
        if not comp_res["success"]:
            return comp_res
        compiled_prog: CompiledProgram = comp_res["_compiled_prog"]
    else:
        compiled_prog = source_or_compiled
        comp_res = None

    # Resolve event timeline
    timeline: List[Tuple[Any, ...]] = []
    if events_spec.strip():
        timeline = resolve_events_timeline(events_spec)
    elif isinstance(source_or_compiled, str):
        timeline = extract_timeline_from_source(source_or_compiled)

    if not timeline and compiled_prog.events:
        t = 0
        timeline = []
        for ev in compiled_prog.events:
            timeline.append((ev, t))
            t += 1000

    simulator = DiscreteEventSimulator(compiled_prog)
    simulator.load_timeline(timeline)
    sim_result: SimulationResult = simulator.run()

    result_dict = {
        "success": sim_result.success,
        "system_name": sim_result.system_name,
        "simulation": {
            "start_time_ms": sim_result.start_time_ms,
            "end_time_ms": sim_result.end_time_ms,
            "duration_ms": sim_result.end_time_ms - sim_result.start_time_ms,
            "total_events": sim_result.total_events_processed,
            "total_state_changes": sim_result.total_state_changes,
        },
        "initial_state": sim_result.initial_state,
        "final_state": sim_result.final_state,
        "events": sim_result.events_log,
        "state_transitions": sim_result.state_transitions,
        "temporal_checks": [t.to_dict() for t in sim_result.temporal_evaluations],
        "summary": {
            "total_events": sim_result.total_events_processed,
            "total_state_changes": sim_result.total_state_changes,
            "constraints_checked": len(sim_result.temporal_evaluations),
            "constraints_satisfied": sim_result.constraints_satisfied,
            "constraints_violated": sim_result.constraints_violated,
            "constraints_timeout": sim_result.constraints_timeout,
            "success": sim_result.success,
        },
        "telemetry_json": sim_result.to_json(indent=2),
        "formatted_log": sim_result.format_display(),
    }

    runtime_diagnostics = []
    for ev in sim_result.temporal_evaluations:
        status_val = getattr(ev, "status", "")
        if status_val in ("VIOLATED", "TIMEOUT"):
            elapsed_str = f"{ev.elapsed_ms}ms" if ev.elapsed_ms is not None else "never occurred"
            runtime_diagnostics.append({
                "stage": "VERIFICATION",
                "severity": "ERROR",
                "line": None,
                "column": None,
                "end_column": None,
                "message": f"Temporal constraint {ev.source_event} -> {ev.target_event} {status_val}: elapsed {elapsed_str} (limit {ev.limit_ms}ms).",
                "explanation": f"Runtime verification detected that event '{ev.target_event}' did not occur within the required {ev.limit_ms}ms limit following '{ev.source_event}'.",
                "suggestion": f"Adjust the event scheduling timeline or increase the constraint deadline if {elapsed_str} is expected.",
            })

    result_dict["diagnostics"] = runtime_diagnostics

    if comp_res is not None:
        # Include compiler stage outputs in response
        result_dict["compiler"] = {k: v for k, v in comp_res.items() if k != "_compiled_prog"}

    return result_dict


def format_seqc_error(err_str: str) -> str:
    """Formats serialization errors into clear, consistent SEQC load error messages."""
    err_lower = err_str.lower()
    if "crc32" in err_lower or "checksum mismatch" in err_lower:
        return f"SEQC LOAD ERROR: CRC32 checksum mismatch. ({err_str})"
    elif "unsupported" in err_lower or "version" in err_lower:
        return f"SEQC LOAD ERROR: Unsupported SEQC version. ({err_str})"
    elif "magic" in err_lower:
        return f"SEQC LOAD ERROR: Invalid SEQC magic header. ({err_str})"
    elif "truncated" in err_lower or "eof" in err_lower:
        return f"SEQC LOAD ERROR: Truncated SEQC payload. ({err_str})"
    return f"SEQC LOAD ERROR: {err_str}"


def execute_seqc_for_ide(raw_bytes: bytes, events_spec: str = "", filename: str = "") -> Dict[str, Any]:
    """Deserializes and directly executes a .seqc binary container via VM/DiscreteEventSimulator.

    This execution path bypasses the lexer, parser, AST, and semantic analyzer, executing
    the pre-compiled bytecode instructions directly.
    """
    if len(raw_bytes) < HEADER_SIZE:
        err_msg = f"SEQC LOAD ERROR: Truncated SEQC payload. Expected at least {HEADER_SIZE} bytes, got {len(raw_bytes)}."
        diag = CompilerDiagnostic(
            stage="SEQC",
            severity="ERROR",
            line=None,
            column=None,
            end_column=None,
            message=err_msg,
            explanation="The provided file is smaller than the required 24-byte SEQUENT binary container header.",
            suggestion="Verify that the file is a valid .seqc binary artifact generated by the SEQUENT compiler.",
        )
        return {
            "success": False,
            "error": {
                "stage": "SEQC",
                "category": "SEQC LOAD ERROR",
                "message": err_msg,
            },
            "diagnostics": [diag.to_dict()],
        }

    try:
        compiled = BytecodeSerializer.deserialize(raw_bytes)
        magic, version, flags, payload_len, crc_expected = struct.unpack(HEADER_STRUCT, raw_bytes[:HEADER_SIZE])
    except SerializationError as e:
        err_msg = format_seqc_error(str(e))
        diag = CompilerDiagnostic(
            stage="SEQC",
            severity="ERROR",
            line=None,
            column=None,
            end_column=None,
            message=err_msg,
            explanation="Deserialization failed. The .seqc container header, version, or CRC32 checksum is invalid.",
            suggestion="Recompile your SEQUENT source to generate a fresh .seqc container with matching checksum.",
        )
        return {
            "success": False,
            "error": {
                "stage": "SEQC",
                "category": "SEQC LOAD ERROR",
                "message": err_msg,
            },
            "diagnostics": [diag.to_dict()],
        }
    except Exception as e:
        err_msg = f"SEQC LOAD ERROR: Corrupted .seqc binary data ({e})"
        diag = CompilerDiagnostic(
            stage="SEQC",
            severity="ERROR",
            line=None,
            column=None,
            end_column=None,
            message=err_msg,
            explanation="The binary payload could not be decoded by the bytecode serializer.",
            suggestion="Recompile the SEQUENT source program.",
        )
        return {
            "success": False,
            "error": {
                "stage": "SEQC",
                "category": "SEQC LOAD ERROR",
                "message": err_msg,
            },
            "diagnostics": [diag.to_dict()],
        }

    # Execute deserialized program directly via simulator (NO lexer/parser/semantic analysis)
    sim_dict = simulate_for_ide(compiled, events_spec=events_spec)

    # Reconstruct bytecode disassembly for the inspector
    bc_instructions = [
        {
            "offset": instr.offset,
            "opcode": instr.opcode.name,
            "arg": repr(instr.arg) if instr.arg is not None else None,
            "source_line": instr.source_line,
            "comment": instr.comment,
        }
        for instr in compiled.instructions
    ]
    bytecode_dict = {
        "instructions": bc_instructions,
        "formatted": format_bytecode(compiled),
        "total_instructions": len(compiled.instructions),
        "handler_table": compiled.handler_table,
    }

    seqc_metadata = {
        "magic": magic.decode("ascii", errors="replace"),
        "version": version,
        "flags": flags,
        "payload_len": payload_len,
        "crc32_hex": f"0x{crc_expected:08X}",
        "total_instructions": len(compiled.instructions),
        "instructions_count": len(compiled.instructions),
        "handler_count": len(compiled.handler_table),
        "handlers_count": len(compiled.handler_table),
        "system_name": compiled.system_name,
    }

    stages_status = {
        "lexer": "skipped",
        "parser": "skipped",
        "symbols": "skipped",
        "semantic": "skipped",
        "temporal": "skipped",
        "ir": "skipped",
        "optimization": "skipped",
        "bytecode": "ok",
        "vm": "ok",
        "simulation": "ok",
        "verification": "ok" if sim_dict.get("summary", {}).get("constraints_violated", 0) == 0 else "failed",
        "timeline": "ok",
        "transitions": "ok",
        "telemetry": "ok",
        "seqc": "ok",
    }

    sim_dict["bytecode"] = bytecode_dict
    sim_dict["seqc_metadata"] = seqc_metadata
    sim_dict["stages_status"] = stages_status
    sim_dict["execution_mode"] = "seqc"
    sim_dict["is_seqc"] = True
    sim_dict["filename"] = filename
    return sim_dict


def get_examples_catalog() -> List[Dict[str, Any]]:
    """Returns curated catalogue of real examples from examples/."""
    examples_dir = WORKSPACE_ROOT / "examples"
    catalog = [
        {
            "id": "valid",
            "name": "Emergency Response System",
            "filename": "valid.seq",
            "default_events": "EmergencyDetected@0ms, TeamDispatched@3200ms, IncidentResolved@5000ms",
            "description": "Standard emergency dispatch coordinator with 5000ms and 30m response constraints.",
        },
        {
            "id": "phase3_simulation",
            "name": "Building Power & Stabilization",
            "filename": "phase3_simulation.seq",
            "default_events": "SensorAlert@0ms, AuxiliaryPowerOnline@1500ms, SystemStabilized@4000ms",
            "description": "Phase 3 reactive power management loop with dual temporal constraints.",
        },
        {
            "id": "phase3_complex",
            "name": "Complex Safety System",
            "filename": "phase3_complex.seq",
            "default_events": "HeartbeatPing@100ms, HeartbeatAck@200ms, FaultDetected@300ms, FailsafeTriggered@450ms",
            "description": "Multi-stage safety monitor verifying multiple concurrent temporal deadlines.",
        },
        {
            "id": "temporal_satisfied",
            "name": "Building Management System",
            "filename": "temporal_satisfied.seq",
            "default_events": "SensorAlert@0ms, AuxiliaryPowerOnline@1500ms, SystemStabilized@4000ms",
            "description": "Smart building automated power grid with satisfied temporal bounds.",
        },
        {
            "id": "temporal_violated",
            "name": "Emergency Response (Violation)",
            "filename": "temporal_violated.seq",
            "default_events": "EmergencyDetected@0ms, TeamDispatched@7200ms, IncidentResolved@8500ms",
            "description": "Emergency coordinator demonstrating runtime constraint VIOLATION (7200ms > 5000ms).",
        },
        {
            "id": "phase3_timeout",
            "name": "Watchdog Timeout System",
            "filename": "phase3_timeout.seq",
            "default_events": "HeartbeatPing@100ms",
            "description": "Watchdog heartbeat demonstrating runtime constraint TIMEOUT condition.",
        },
        {
            "id": "optimization_demo",
            "name": "Smart Grid Controller (Optimizer)",
            "filename": "optimization_demo.seq",
            "default_events": "GridFault@0ms",
            "description": "Redundant assignment pattern demonstrating Dead Store Elimination pass.",
        },
        {
            "id": "syntax_error",
            "name": "Syntax Error Demo",
            "filename": "syntax_error.seq",
            "default_events": "EventA@0ms",
            "description": "Intentional syntax error (missing closing brace) testing parser diagnostics.",
        },
        {
            "id": "semantic_error",
            "name": "Semantic Error Demo",
            "filename": "semantic_error.seq",
            "default_events": "UndefinedEvent@0ms",
            "description": "Intentional semantic error (undeclared event) testing scope diagnostics.",
        },
        {
            "id": "temporal_error",
            "name": "Temporal Error Demo",
            "filename": "temporal_error.seq",
            "default_events": "EventA@0ms",
            "description": "Intentional temporal constraint error testing static constraint validation.",
        },
        {
            "id": "type_error",
            "name": "Type Mismatch Demo",
            "filename": "type_error.seq",
            "default_events": "EventA@0ms",
            "description": "Intentional type error (assigning string to integer state) testing type checker.",
        },
    ]

    for item in catalog:
        file_path = examples_dir / item["filename"]
        if file_path.is_file():
            item["source"] = file_path.read_text(encoding="utf-8")
        else:
            item["source"] = ""

    return catalog


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler providing REST API endpoints and static file serving."""

    def _set_headers(self, status_code: int = 200, content_type: str = "application/json"):
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        """Handle CORS pre-flight requests."""
        self._set_headers(204, "text/plain")

    def _read_json_body(self) -> Dict[str, Any]:
        """Reads and parses JSON payload from request body."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            return {}
        raw = self.rfile.read(content_length).decode("utf-8")
        return json.loads(raw)

    def _serve_file(self, file_path: Path, content_type: str):
        """Serves static file content."""
        if not file_path.is_file():
            self._set_headers(404, "text/plain")
            self.wfile.write(b"404 Not Found")
            return
        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        dashboard_dir = WORKSPACE_ROOT / "dashboard"

        if path in ("/", "/index.html"):
            self._serve_file(dashboard_dir / "index.html", "text/html; charset=utf-8")
        elif path == "/style.css":
            self._serve_file(dashboard_dir / "style.css", "text/css; charset=utf-8")
        elif path == "/app.js":
            self._serve_file(dashboard_dir / "app.js", "application/javascript; charset=utf-8")
        elif path == "/favicon.ico":
            ico_file = dashboard_dir / "favicon.ico"
            svg_file = dashboard_dir / "favicon.svg"
            if ico_file.is_file():
                self._serve_file(ico_file, "image/x-icon")
            elif svg_file.is_file():
                self._serve_file(svg_file, "image/svg+xml")
            else:
                self.send_response(204)
                self.end_headers()
        elif path == "/favicon.svg":
            svg_file = dashboard_dir / "favicon.svg"
            if svg_file.is_file():
                self._serve_file(svg_file, "image/svg+xml")
            else:
                self.send_response(404)
                self.end_headers()
        elif path == "/api/health":
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "system": "SEQUENT Compiler", "version": "Phase 3 Integrated"}).encode("utf-8"))
        elif path == "/api/examples":
            catalog = get_examples_catalog()
            self._set_headers(200)
            self.wfile.write(json.dumps(catalog).encode("utf-8"))
        elif path == "/api/templates":
            self._set_headers(200)
            self.wfile.write(json.dumps(list(TEMPLATES.values())).encode("utf-8"))
        else:
            # Check if static file inside dashboard/
            candidate = dashboard_dir / path.lstrip("/")
            if candidate.is_file():
                ext = candidate.suffix.lower()
                c_type = "text/plain"
                if ext == ".html":
                    c_type = "text/html; charset=utf-8"
                elif ext == ".css":
                    c_type = "text/css; charset=utf-8"
                elif ext == ".js":
                    c_type = "application/javascript; charset=utf-8"
                elif ext == ".svg":
                    c_type = "image/svg+xml"
                elif ext == ".ico":
                    c_type = "image/x-icon"
                elif ext == ".json":
                    c_type = "application/json"
                self._serve_file(candidate, c_type)
            else:
                self._set_headers(404, "application/json")
                self.wfile.write(json.dumps({"error": f"Path '{path}' not found."}).encode("utf-8"))

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        try:
            body = self._read_json_body()
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"success": False, "error": f"Invalid JSON payload: {e}"}).encode("utf-8"))
            return

        if path == "/api/compile":
            source = body.get("source", "")
            optimize = bool(body.get("optimize", False))
            result = compile_for_ide(source, optimize=optimize)
            # Remove private object before serialization
            result.pop("_compiled_prog", None)
            self._set_headers(200)
            self.wfile.write(json.dumps(result).encode("utf-8"))

        elif path in ("/api/run", "/api/simulate"):
            source = body.get("source", "")
            events = body.get("events", "")
            optimize = bool(body.get("optimize", False))
            result = simulate_for_ide(source, events_spec=events, optimize=optimize)
            self._set_headers(200)
            self.wfile.write(json.dumps(result).encode("utf-8"))

        elif path == "/api/compile-run":
            source = body.get("source", "")
            events = body.get("events", "")
            optimize = bool(body.get("optimize", False))
            result = simulate_for_ide(source, events_spec=events, optimize=optimize)
            self._set_headers(200)
            self.wfile.write(json.dumps(result).encode("utf-8"))

        elif path == "/api/emit-seqc":
            source = body.get("source", "")
            optimize = bool(body.get("optimize", False))
            comp_res = compile_for_ide(source, optimize=optimize)
            if not comp_res["success"]:
                comp_res.pop("_compiled_prog", None)
                self._set_headers(200)
                self.wfile.write(json.dumps(comp_res).encode("utf-8"))
                return

            compiled: CompiledProgram = comp_res["_compiled_prog"]
            raw_bytes = BytecodeSerializer.serialize(compiled)
            magic, version, flags, payload_len, crc_expected = struct.unpack(HEADER_STRUCT, raw_bytes[:HEADER_SIZE])

            response = {
                "success": True,
                "system_name": compiled.system_name,
                "filename": f"{compiled.system_name}.seqc",
                "size_bytes": len(raw_bytes),
                "magic": magic.decode("ascii", errors="replace"),
                "version": version,
                "flags": flags,
                "payload_len": payload_len,
                "crc32_hex": f"0x{crc_expected:08X}",
                "total_instructions": len(compiled.instructions),
                "base64_data": base64.b64encode(raw_bytes).decode("ascii"),
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(response).encode("utf-8"))

        elif path in ("/api/load-seqc", "/api/run-seqc"):
            b64_data = body.get("base64_data", "")
            events = body.get("events", "")
            try:
                raw_bytes = base64.b64decode(b64_data)
            except Exception as e:
                self._set_headers(200)
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": {
                        "stage": "SEQC",
                        "category": "SEQC LOAD ERROR",
                        "message": f"SEQC LOAD ERROR: Base64 decoding failed: {e}",
                    }
                }).encode("utf-8"))
                return

            filename = body.get("filename", "")
            res = execute_seqc_for_ide(raw_bytes, events_spec=events, filename=filename)
            self._set_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))

        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": f"Endpoint '{path}' not found."}).encode("utf-8"))

    def log_message(self, format, *args):
        """Quiet logging for clean terminal output."""
        return


def create_app_server(host: str = "127.0.0.1", port: int = 8000) -> HTTPServer:
    """Creates and returns the configured HTTPServer instance."""
    return HTTPServer((host, port), DashboardRequestHandler)


def main():
    parser = argparse.ArgumentParser(description="SEQUENT Compiler - Web IDE & Execution Dashboard Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    args = parser.parse_args()

    server = create_app_server(args.host, args.port)
    url = f"http://{args.host}:{args.port}"
    print("=" * 60)
    print("SEQUENT Web IDE & Compiler Dashboard")
    print(f"URL: {url}")
    print(f"Workspace: {WORKSPACE_ROOT}")
    print("Status: READY")
    print("=" * 60)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down SEQUENT Web IDE server...")
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
