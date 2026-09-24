"""
SEQUENT Compiler - Bytecode Instruction Set & Generator
Defines the stack-based VM bytecode instruction set and compilation from IR.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from compiler.ir import IRProgram, IROpCode


class OpCode(Enum):
    """OpCodes for the SEQUENT Virtual Machine."""
    PUSH_CONST = auto()       # Push literal constant onto operand stack
    POP = auto()              # Discard top value on operand stack
    STORE_STATE = auto()      # Pop value and store into named state variable
    LOAD_STATE = auto()       # Load value of named state variable onto operand stack
    ENTER_HANDLER = auto()    # Enter event handler scope
    EXIT_HANDLER = auto()     # Exit event handler scope
    EMIT_EVENT = auto()       # Dispatch an event at simulated virtual clock time
    CHECK_TEMPORAL = auto()   # Perform runtime temporal constraint check
    HALT = auto()             # Halt virtual machine execution

    def __str__(self) -> str:
        return self.name


@dataclass
class BytecodeInstruction:
    """A single executable bytecode instruction for the SEQUENT VM."""
    offset: int
    opcode: OpCode
    arg: Any = None
    source_line: int = 0
    comment: str = ""

    def __repr__(self) -> str:
        arg_str = f" {self.arg!r}" if self.arg is not None else ""
        return f"{self.offset:04d}: {self.opcode.name:<16}{arg_str}"


@dataclass
class CompiledProgram:
    """A fully compiled SEQUENT program ready for execution on the VM."""
    system_name: str
    initial_states: Dict[str, Any]
    state_types: Dict[str, str]
    events: List[str]
    constraints: List[Dict[str, Any]]
    instructions: List[BytecodeInstruction]
    handler_table: Dict[str, int]  # event_name -> bytecode offset


class BytecodeGenerator:
    """Compiles Intermediate Representation (IR) into SEQUENT Bytecode."""

    def __init__(self):
        self.instructions: List[BytecodeInstruction] = []
        self.handler_table: Dict[str, int] = {}

    def generate(self, ir_prog: IRProgram) -> CompiledProgram:
        """Transforms an IRProgram into a CompiledProgram with bytecode instructions."""
        self.instructions = []
        self.handler_table = {}

        initial_states = {k: v.initial_value for k, v in ir_prog.states.items()}
        state_types = {k: v.inferred_type for k, v in ir_prog.states.items()}

        constraints = [
            {
                "source": c.source_event,
                "target": c.target_event,
                "duration_ms": c.duration_ms,
                "raw_duration": c.raw_duration,
                "line": c.line,
            }
            for c in ir_prog.constraints
        ]

        offset = 0
        for ir_inst in ir_prog.instructions:
            if ir_inst.opcode == IROpCode.LABEL_HANDLER:
                handler_name = ir_inst.arg1
                self.handler_table[handler_name] = offset
                self.instructions.append(
                    BytecodeInstruction(
                        offset=offset,
                        opcode=OpCode.ENTER_HANDLER,
                        arg=handler_name,
                        source_line=ir_inst.source_line,
                        comment=f"Enter on {handler_name}",
                    )
                )
                offset += 1

            elif ir_inst.opcode == IROpCode.STORE_STATE:
                # 1. PUSH_CONST <val>
                self.instructions.append(
                    BytecodeInstruction(
                        offset=offset,
                        opcode=OpCode.PUSH_CONST,
                        arg=ir_inst.arg2,
                        source_line=ir_inst.source_line,
                        comment=f"Push literal {ir_inst.arg2!r}",
                    )
                )
                offset += 1

                # 2. STORE_STATE <name>
                self.instructions.append(
                    BytecodeInstruction(
                        offset=offset,
                        opcode=OpCode.STORE_STATE,
                        arg=ir_inst.arg1,
                        source_line=ir_inst.source_line,
                        comment=f"Store to state '{ir_inst.arg1}'",
                    )
                )
                offset += 1

            elif ir_inst.opcode == IROpCode.END_HANDLER:
                self.instructions.append(
                    BytecodeInstruction(
                        offset=offset,
                        opcode=OpCode.EXIT_HANDLER,
                        arg=ir_inst.arg1,
                        source_line=ir_inst.source_line,
                        comment=f"Exit on {ir_inst.arg1}",
                    )
                )
                offset += 1

            elif ir_inst.opcode == IROpCode.EMIT_EVENT:
                self.instructions.append(
                    BytecodeInstruction(
                        offset=offset,
                        opcode=OpCode.EMIT_EVENT,
                        arg=(ir_inst.arg1, ir_inst.arg2),
                        source_line=ir_inst.source_line,
                        comment=f"Emit {ir_inst.arg1} at {ir_inst.arg2}ms",
                    )
                )
                offset += 1

            elif ir_inst.opcode == IROpCode.CHECK_CONSTRAINT:
                self.instructions.append(
                    BytecodeInstruction(
                        offset=offset,
                        opcode=OpCode.CHECK_TEMPORAL,
                        arg=(ir_inst.arg1, ir_inst.arg2, ir_inst.arg3),
                        source_line=ir_inst.source_line,
                        comment=f"Check {ir_inst.arg1} -> {ir_inst.arg2} within {ir_inst.arg3}ms",
                    )
                )
                offset += 1

            elif ir_inst.opcode == IROpCode.NOP:
                pass  # Skip NOPs in bytecode

        # Final HALT instruction
        self.instructions.append(
            BytecodeInstruction(
                offset=offset,
                opcode=OpCode.HALT,
                arg=None,
                source_line=0,
                comment="Halt VM execution",
            )
        )

        return CompiledProgram(
            system_name=ir_prog.system_name,
            initial_states=initial_states,
            state_types=state_types,
            events=list(ir_prog.events),
            constraints=constraints,
            instructions=self.instructions,
            handler_table=self.handler_table,
        )


def format_bytecode(compiled: CompiledProgram) -> str:
    """Produces a clean disassembly table of generated bytecode for CLI inspection."""
    lines: List[str] = [
        "============================================================",
        "                     SEQUENT BYTECODE                       ",
        "============================================================",
        f"SYSTEM: {compiled.system_name}",
        f"Total Instructions: {len(compiled.instructions)}",
        f"Handlers Registered: {len(compiled.handler_table)}",
        "",
        f"  {'Offset':<8} {'Opcode':<18} {'Operand':<22} {'Source':<12}",
        f"  {'-'*8} {'-'*18} {'-'*22} {'-'*12}",
    ]

    for inst in compiled.instructions:
        arg_val = "-" if inst.arg is None else repr(inst.arg)
        loc = f"Line {inst.source_line}" if inst.source_line > 0 else "-"
        lines.append(f"  {inst.offset:04d}     {inst.opcode.name:<18} {arg_val:<22} {loc:<12}")

    lines.append("============================================================")
    return "\n".join(lines)
