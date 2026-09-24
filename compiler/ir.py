"""
SEQUENT Compiler - Intermediate Representation (IR)
Defines the linear IR instruction set, IR data structures, and AST-to-IR generation.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from compiler.ast import (
    ProgramNode,
    StateDeclNode,
    EventDeclNode,
    HandlerNode,
    AssignmentNode,
    ConstraintNode,
)
from compiler.symbol_table import SymbolTable


class IROpCode(Enum):
    """OpCodes for SEQUENT Intermediate Representation."""
    DECLARE_STATE = auto()
    DECLARE_EVENT = auto()
    DECLARE_CONSTRAINT = auto()
    LABEL_HANDLER = auto()
    STORE_STATE = auto()
    EMIT_EVENT = auto()
    CHECK_CONSTRAINT = auto()
    END_HANDLER = auto()
    NOP = auto()

    def __str__(self) -> str:
        return self.name


UNIT_MULTIPLIERS = {
    "ms": 1,
    "s": 1000,
    "m": 60000,
    "h": 3600000,
}


@dataclass
class IRInstruction:
    """A linear 3-address style IR instruction."""
    opcode: IROpCode
    arg1: Any = None
    arg2: Any = None
    arg3: Any = None
    source_line: int = 0
    comment: str = ""

    def __repr__(self) -> str:
        parts = [self.opcode.name]
        if self.arg1 is not None:
            parts.append(str(self.arg1))
        if self.arg2 is not None:
            parts.append(repr(self.arg2))
        if self.arg3 is not None:
            parts.append(str(self.arg3))
        return " ".join(parts)


@dataclass
class IRStateDecl:
    name: str
    inferred_type: str
    initial_value: Any
    line: int = 0


@dataclass
class IRConstraint:
    source_event: str
    target_event: str
    raw_duration: str
    duration_ms: int
    line: int = 0


@dataclass
class IRProgram:
    """Complete IR representation of a SEQUENT system."""
    system_name: str
    states: Dict[str, IRStateDecl] = field(default_factory=dict)
    events: List[str] = field(default_factory=list)
    constraints: List[IRConstraint] = field(default_factory=list)
    instructions: List[IRInstruction] = field(default_factory=list)
    handler_offsets: Dict[str, int] = field(default_factory=dict)


class IRGenerator:
    """Translates a semantically verified SEQUENT AST into linear Intermediate Representation."""

    def __init__(self):
        self.ir: Optional[IRProgram] = None

    def generate(self, ast: ProgramNode, symbol_table: Optional[SymbolTable] = None) -> IRProgram:
        """Generates an IRProgram from the given AST ProgramNode."""
        self.ir = IRProgram(system_name=ast.system_name)

        # 1. Process state and event declarations
        for decl in ast.declarations:
            if isinstance(decl, StateDeclNode):
                lit_val = decl.initial_value.value
                lit_type = decl.initial_value.lit_type
                state_decl = IRStateDecl(
                    name=decl.name,
                    inferred_type=lit_type,
                    initial_value=lit_val,
                    line=decl.line,
                )
                self.ir.states[decl.name] = state_decl
            elif isinstance(decl, EventDeclNode):
                self.ir.events.append(decl.name)

        # 2. Process temporal constraints
        for c in ast.constraints:
            mult = UNIT_MULTIPLIERS.get(c.duration.unit, 1000)
            duration_ms = c.duration.amount * mult
            raw_dur = f"{c.duration.amount}{c.duration.unit}"
            ir_c = IRConstraint(
                source_event=c.source_event,
                target_event=c.target_event,
                raw_duration=raw_dur,
                duration_ms=duration_ms,
                line=c.line,
            )
            self.ir.constraints.append(ir_c)

        # 3. Generate instructions for handlers
        for handler in ast.handlers:
            handler_idx = len(self.ir.instructions)
            self.ir.handler_offsets[handler.event_name] = handler_idx

            # Handler entry label
            self.ir.instructions.append(
                IRInstruction(
                    opcode=IROpCode.LABEL_HANDLER,
                    arg1=handler.event_name,
                    source_line=handler.line,
                    comment=f"Entry for on {handler.event_name}",
                )
            )

            # Handler assignments
            for assign in handler.assignments:
                self.ir.instructions.append(
                    IRInstruction(
                        opcode=IROpCode.STORE_STATE,
                        arg1=assign.state_name,
                        arg2=assign.value.value,
                        arg3=assign.value.lit_type,
                        source_line=assign.line,
                        comment=f"{assign.state_name} = {assign.value.value!r}",
                    )
                )

            # Handler exit
            self.ir.instructions.append(
                IRInstruction(
                    opcode=IROpCode.END_HANDLER,
                    arg1=handler.event_name,
                    source_line=handler.line,
                    comment=f"Exit for on {handler.event_name}",
                )
            )

        return self.ir


def format_ir(ir_prog: IRProgram) -> str:
    """Produces a clean, human-readable representation of the IR for CLI inspection."""
    lines: List[str] = [
        "============================================================",
        "              INTERMEDIATE REPRESENTATION (IR)              ",
        "============================================================",
        f"SYSTEM: {ir_prog.system_name}",
        "",
        "STATE DECLARATIONS:",
    ]

    if not ir_prog.states:
        lines.append("  (none)")
    else:
        for s in ir_prog.states.values():
            val_str = f'"{s.initial_value}"' if s.inferred_type == "string" else str(s.initial_value).lower() if s.inferred_type == "bool" else str(s.initial_value)
            lines.append(f"  DECLARE_STATE   {s.name:<16} : {s.inferred_type:<8} = {val_str}")

    lines.extend(["", "EVENT DECLARATIONS:"])
    if not ir_prog.events:
        lines.append("  (none)")
    else:
        for e in ir_prog.events:
            lines.append(f"  DECLARE_EVENT   {e}")

    lines.extend(["", "TEMPORAL CONSTRAINTS:"])
    if not ir_prog.constraints:
        lines.append("  (none)")
    else:
        for c in ir_prog.constraints:
            lines.append(f"  IR_CONSTRAINT   {c.source_event} -> {c.target_event} [within {c.raw_duration} / {c.duration_ms:,} ms]")

    lines.extend(["", "IR INSTRUCTION STREAM:"])
    if not ir_prog.instructions:
        lines.append("  (none)")
    else:
        for idx, inst in enumerate(ir_prog.instructions):
            if inst.opcode == IROpCode.LABEL_HANDLER:
                lines.append(f"  [{idx:02d}] LABEL_HANDLER {inst.arg1}")
            elif inst.opcode == IROpCode.STORE_STATE:
                val_str = f'"{inst.arg2}"' if inst.arg3 == "string" else str(inst.arg2).lower() if inst.arg3 == "bool" else str(inst.arg2)
                lines.append(f"  [{idx:02d}]   STORE_STATE   {inst.arg1:<16} , {val_str}")
            elif inst.opcode == IROpCode.END_HANDLER:
                lines.append(f"  [{idx:02d}] END_HANDLER   {inst.arg1}")
            elif inst.opcode == IROpCode.EMIT_EVENT:
                lines.append(f"  [{idx:02d}]   EMIT_EVENT    {inst.arg1:<16} (delay: {inst.arg2}ms)")
            elif inst.opcode == IROpCode.CHECK_CONSTRAINT:
                lines.append(f"  [{idx:02d}]   CHECK_LIMIT   {inst.arg1} -> {inst.arg2} <= {inst.arg3}ms")
            elif inst.opcode == IROpCode.NOP:
                lines.append(f"  [{idx:02d}]   NOP")
            else:
                lines.append(f"  [{idx:02d}] {inst}")

    lines.append("============================================================")
    return "\n".join(lines)
