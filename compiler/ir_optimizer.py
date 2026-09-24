"""
SEQUENT Compiler - IR Optimizer
Performs dead-store elimination, redundant consecutive store removal,
and no-op pruning on the linear IR.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import copy

from compiler.ir import IRProgram, IRInstruction, IROpCode


@dataclass
class OptimizationStats:
    """Statistics on transformations performed during IR optimization."""
    initial_instructions: int = 0
    final_instructions: int = 0
    redundant_stores_removed: int = 0
    nops_pruned: int = 0
    passes_run: int = 0
    details: List[str] = field(default_factory=list)

    @property
    def instructions_eliminated(self) -> int:
        return self.initial_instructions - self.final_instructions

    @property
    def percentage_reduction(self) -> float:
        if self.initial_instructions == 0:
            return 0.0
        return (self.instructions_eliminated / self.initial_instructions) * 100.0


class IROptimizer:
    """Performs safe, demonstrable optimization passes on SEQUENT IR."""

    def __init__(self):
        self.stats = OptimizationStats()

    def optimize(self, ir_prog: IRProgram) -> Tuple[IRProgram, OptimizationStats]:
        """Runs optimization passes on the IRProgram and returns an optimized copy and stats."""
        opt_ir = copy.deepcopy(ir_prog)
        self.stats = OptimizationStats()
        self.stats.initial_instructions = len(opt_ir.instructions)

        # Pass 1: Redundant Consecutive Store Elimination within Handlers
        self._eliminate_dead_stores(opt_ir)

        # Pass 2: NOP Pruning
        self._prune_nops(opt_ir)

        # Rebuild handler offsets
        self._rebuild_handler_offsets(opt_ir)

        self.stats.final_instructions = len(opt_ir.instructions)
        return opt_ir, self.stats

    def _eliminate_dead_stores(self, opt_ir: IRProgram) -> None:
        """Eliminates redundant consecutive assignments to the same state variable

        within the same handler block.
        Example:
          STORE_STATE x, 1
          STORE_STATE x, 2
        Here, the first store is dead because 'x' is overwritten before any observation.
        """
        self.stats.passes_run += 1
        instructions = opt_ir.instructions
        n = len(instructions)
        i = 0

        while i < n:
            if instructions[i].opcode == IROpCode.LABEL_HANDLER:
                handler_name = instructions[i].arg1
                # Collect stores in this handler until END_HANDLER
                j = i + 1
                last_store_idx: Dict[str, int] = {}

                while j < n and instructions[j].opcode != IROpCode.END_HANDLER:
                    inst = instructions[j]
                    if inst.opcode == IROpCode.STORE_STATE:
                        state_var = inst.arg1
                        if state_var in last_store_idx:
                            # Prior store to same variable without intervening read/handler exit
                            prev_idx = last_store_idx[state_var]
                            prev_val = instructions[prev_idx].arg2
                            new_val = inst.arg2
                            instructions[prev_idx] = IRInstruction(
                                opcode=IROpCode.NOP,
                                comment=f"Eliminated dead store to '{state_var}' (overwritten by {new_val!r})",
                            )
                            self.stats.redundant_stores_removed += 1
                            self.stats.details.append(
                                f"Handler '{handler_name}': Eliminated redundant store '{state_var} = {prev_val!r}' (overwritten by {new_val!r})"
                            )
                        last_store_idx[state_var] = j
                    j += 1
                i = j
            i += 1

    def _prune_nops(self, opt_ir: IRProgram) -> None:
        """Prunes NOP instructions from the stream."""
        self.stats.passes_run += 1
        original = opt_ir.instructions
        pruned: List[IRInstruction] = []
        for inst in original:
            if inst.opcode == IROpCode.NOP:
                self.stats.nops_pruned += 1
            else:
                pruned.append(inst)
        opt_ir.instructions = pruned

    def _rebuild_handler_offsets(self, opt_ir: IRProgram) -> None:
        """Reconstructs the handler_offsets map based on new instruction indices."""
        opt_ir.handler_offsets.clear()
        for idx, inst in enumerate(opt_ir.instructions):
            if inst.opcode == IROpCode.LABEL_HANDLER:
                opt_ir.handler_offsets[inst.arg1] = idx


def format_optimization_comparison(orig_ir: IRProgram, opt_ir: IRProgram, stats: OptimizationStats) -> str:
    """Produces a formatted before/after comparison table for CLI inspection."""
    lines: List[str] = [
        "============================================================",
        "                 IR OPTIMIZATION COMPARISON                 ",
        "============================================================",
        f"Optimization Passes Executed: {stats.passes_run}",
        f"Initial IR Instruction Count: {stats.initial_instructions}",
        f"Final IR Instruction Count:   {stats.final_instructions}",
        f"Instructions Eliminated:      {stats.instructions_eliminated} ({stats.percentage_reduction:.1f}% reduction)",
        f"Redundant Stores Removed:     {stats.redundant_stores_removed}",
        f"NOPs Pruned:                  {stats.nops_pruned}",
        "",
        "TRANSFORMATION LOG:",
    ]

    if not stats.details:
        lines.append("  (no redundant instructions detected - IR is already canonical)")
    else:
        for detail in stats.details:
            lines.append(f"  ✓ {detail}")

    lines.extend([
        "",
        "------------------------------------------------------------",
        "OPTIMIZED IR INSTRUCTION STREAM:",
        "------------------------------------------------------------",
    ])

    for idx, inst in enumerate(opt_ir.instructions):
        if inst.opcode == IROpCode.LABEL_HANDLER:
            lines.append(f"  [{idx:02d}] LABEL_HANDLER {inst.arg1}")
        elif inst.opcode == IROpCode.STORE_STATE:
            val_str = f'"{inst.arg2}"' if inst.arg3 == "string" else str(inst.arg2).lower() if inst.arg3 == "bool" else str(inst.arg2)
            lines.append(f"  [{idx:02d}]   STORE_STATE   {inst.arg1:<16} , {val_str}")
        elif inst.opcode == IROpCode.END_HANDLER:
            lines.append(f"  [{idx:02d}] END_HANDLER   {inst.arg1}")
        else:
            lines.append(f"  [{idx:02d}] {inst}")

    lines.append("============================================================")
    return "\n".join(lines)
