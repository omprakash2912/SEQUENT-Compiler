"""
SEQUENT Compiler - Temporal Constraint Analyzer
Performs Phase 1 static validation of temporal constraints:
- Verifies existence of source and target events
- Rejects non-positive durations
- Normalizes durations to milliseconds
- Registers verified temporal constraints
"""

from dataclasses import dataclass
from typing import List, Optional
from compiler.ast import ProgramNode
from compiler.symbol_table import SymbolTable

UNIT_MULTIPLIERS = {
    "ms": 1,
    "s": 1000,
    "m": 60000,
    "h": 3600000,
}


class TemporalError(Exception):
    """Exception raised for temporal constraint errors during analysis."""

    def __init__(self, message: str, line: Optional[int] = None, column: Optional[int] = None):
        self.message = message
        self.line = line
        self.column = column
        loc = f" at line {line}, column {column}" if line is not None and column is not None else ""
        super().__init__(f"TEMPORAL ERROR: {message}{loc}")


@dataclass
class TemporalConstraintRecord:
    """Represents a validated static temporal constraint."""
    source_event: str
    target_event: str
    raw_duration: str
    duration_ms: int
    line: int
    column: int

    def __repr__(self) -> str:
        return f"{self.source_event} -> {self.target_event} within {self.raw_duration} ({self.duration_ms}ms)"


class TemporalAnalyzer:
    """Performs static temporal constraint validation on the AST."""

    def __init__(self):
        self.constraints: List[TemporalConstraintRecord] = []

    def analyze(self, program: ProgramNode, symbol_table: SymbolTable) -> List[TemporalConstraintRecord]:
        """Validates temporal constraints against the symbol table and normalizes durations."""
        self.constraints = []

        for c in program.constraints:
            # 1. Verify source event exists
            if not symbol_table.has_event(c.source_event):
                raise TemporalError(
                    f"Undefined event '{c.source_event}' in temporal constraint.",
                    c.line,
                    c.column,
                )

            # 2. Verify target event exists
            if not symbol_table.has_event(c.target_event):
                raise TemporalError(
                    f"Undefined event '{c.target_event}' in temporal constraint.",
                    c.line,
                    c.column,
                )

            # 3. Reject non-positive duration
            if c.duration.amount <= 0:
                raise TemporalError(
                    f"Non-positive duration '{c.duration.amount}{c.duration.unit}' in temporal constraint. Duration must be strictly positive.",
                    c.duration.line,
                    c.duration.column,
                )

            # 4. Check unit and normalize to milliseconds
            unit = c.duration.unit
            if unit not in UNIT_MULTIPLIERS:
                raise TemporalError(
                    f"Invalid duration unit '{unit}'. Supported units are ms, s, m, h.",
                    c.duration.line,
                    c.duration.column,
                )

            duration_ms = c.duration.amount * UNIT_MULTIPLIERS[unit]
            record = TemporalConstraintRecord(
                source_event=c.source_event,
                target_event=c.target_event,
                raw_duration=f"{c.duration.amount}{c.duration.unit}",
                duration_ms=duration_ms,
                line=c.line,
                column=c.column,
            )
            self.constraints.append(record)

        return self.constraints

    def format_display(self) -> str:
        """Produces a formatted, readable table of registered temporal constraints."""
        lines: List[str] = [
            "================================================================================",
            "                        TEMPORAL CONSTRAINTS (STATIC)                           ",
            "================================================================================",
            f"  {'Source Event':<22} {'Target Event':<22} {'Raw':<8} {'Normalized (ms)':<16} {'Location':<14}",
            f"  {'-'*22} {'-'*22} {'-'*8} {'-'*16} {'-'*14}",
        ]

        if not self.constraints:
            lines.append("  (no constraints defined)")
        else:
            for r in self.constraints:
                loc = f"Line {r.line}, Col {r.column}"
                norm_str = f"{r.duration_ms:,} ms"
                lines.append(f"  {r.source_event:<22} {r.target_event:<22} {r.raw_duration:<8} {norm_str:<16} {loc:<14}")

        lines.append("================================================================================")
        return "\n".join(lines)
