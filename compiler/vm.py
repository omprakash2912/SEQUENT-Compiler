"""
SEQUENT Compiler - Virtual Machine (VM)
A stack-based virtual machine executing SEQUENT bytecode with state tracking.
"""

from typing import Any, Dict, List, Optional, Tuple
from compiler.bytecode import BytecodeInstruction, CompiledProgram, OpCode


class VMError(Exception):
    """Exception raised for runtime errors during virtual machine execution."""
    def __init__(self, message: str, offset: int = -1):
        self.message = message
        self.offset = offset
        loc = f" at bytecode offset {offset:04d}" if offset >= 0 else ""
        super().__init__(f"RUNTIME VM ERROR: {message}{loc}")


class VirtualMachine:
    """Stack-based execution engine for SEQUENT bytecode."""

    def __init__(self, compiled_prog: CompiledProgram):
        self.program = compiled_prog
        self.states: Dict[str, Any] = dict(compiled_prog.initial_states)
        self.stack: List[Any] = []
        self.pc: int = 0
        self.halted: bool = False
        self.active_handler: Optional[str] = None

    def reset(self) -> None:
        """Resets the VM to initial state."""
        self.states = dict(self.program.initial_states)
        self.stack.clear()
        self.pc = 0
        self.halted = False
        self.active_handler = None

    def execute_handler(self, event_name: str) -> List[Tuple[str, Any, Any]]:
        """Executes the handler registered for the given event name.

        Returns a list of state changes: [(var_name, old_val, new_val), ...]
        """
        if event_name not in self.program.handler_table:
            return []

        start_offset = self.program.handler_table[event_name]
        self.pc = start_offset
        state_changes: List[Tuple[str, Any, Any]] = []

        while self.pc < len(self.program.instructions):
            inst = self.program.instructions[self.pc]

            if inst.opcode == OpCode.ENTER_HANDLER:
                self.active_handler = inst.arg
                self.pc += 1

            elif inst.opcode == OpCode.PUSH_CONST:
                self.stack.append(inst.arg)
                self.pc += 1

            elif inst.opcode == OpCode.POP:
                if not self.stack:
                    raise VMError("Operand stack underflow on POP", self.pc)
                self.stack.pop()
                self.pc += 1

            elif inst.opcode == OpCode.LOAD_STATE:
                var_name = inst.arg
                if var_name not in self.states:
                    raise VMError(f"Undefined state variable '{var_name}'", self.pc)
                self.stack.append(self.states[var_name])
                self.pc += 1

            elif inst.opcode == OpCode.STORE_STATE:
                if not self.stack:
                    raise VMError("Operand stack underflow on STORE_STATE", self.pc)
                var_name = inst.arg
                new_val = self.stack.pop()
                old_val = self.states.get(var_name)
                self.states[var_name] = new_val
                state_changes.append((var_name, old_val, new_val))
                self.pc += 1

            elif inst.opcode == OpCode.EXIT_HANDLER:
                self.active_handler = None
                self.pc += 1
                break  # Finished executing this handler block

            elif inst.opcode == OpCode.HALT:
                self.halted = True
                break

            else:
                self.pc += 1

        return state_changes
