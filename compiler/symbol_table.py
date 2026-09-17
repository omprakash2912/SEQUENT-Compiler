"""
SEQUENT Compiler - Symbol Table
Stores state and event symbols with type information, initial values, and declaration locations.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, List


@dataclass
class StateSymbol:
    """Represents a declared state variable."""
    name: str
    inferred_type: str
    initial_value: Any
    line: int
    column: int

    def __repr__(self) -> str:
        return f"StateSymbol({self.name}: {self.inferred_type} = {self.initial_value!r})"


@dataclass
class EventSymbol:
    """Represents a declared event."""
    name: str
    line: int
    column: int

    def __repr__(self) -> str:
        return f"EventSymbol({self.name})"


class SymbolTable:
    """Symbol Table managing state and event definitions in a SEQUENT system."""

    def __init__(self):
        self.states: Dict[str, StateSymbol] = {}
        self.events: Dict[str, EventSymbol] = {}

    def define_state(self, name: str, inferred_type: str, initial_value: Any, line: int, column: int) -> bool:
        """Defines a new state symbol. Returns False if name is already defined."""
        if self.has_state(name) or self.has_event(name):
            return False
        self.states[name] = StateSymbol(
            name=name,
            inferred_type=inferred_type,
            initial_value=initial_value,
            line=line,
            column=column,
        )
        return True

    def define_event(self, name: str, line: int, column: int) -> bool:
        """Defines a new event symbol. Returns False if name is already defined."""
        if self.has_event(name) or self.has_state(name):
            return False
        self.events[name] = EventSymbol(
            name=name,
            line=line,
            column=column,
        )
        return True

    def lookup_state(self, name: str) -> Optional[StateSymbol]:
        """Looks up a state symbol by name."""
        return self.states.get(name)

    def lookup_event(self, name: str) -> Optional[EventSymbol]:
        """Looks up an event symbol by name."""
        return self.events.get(name)

    def has_state(self, name: str) -> bool:
        """Checks whether a state symbol exists."""
        return name in self.states

    def has_event(self, name: str) -> bool:
        """Checks whether an event symbol exists."""
        return name in self.events

    def format_display(self) -> str:
        """Produces a formatted, readable string of the symbol table for CLI inspection."""
        lines: List[str] = [
            "============================================================",
            "                       SYMBOL TABLE                         ",
            "============================================================",
            "STATES:",
            f"  {'Name':<16} {'Type':<10} {'Initial Value':<18} {'Location':<14}",
            f"  {'-'*16} {'-'*10} {'-'*18} {'-'*14}",
        ]

        if not self.states:
            lines.append("  (none)")
        else:
            for s in self.states.values():
                val_repr = f'"{s.initial_value}"' if s.inferred_type == "string" else str(s.initial_value)
                loc = f"Line {s.line}, Col {s.column}"
                lines.append(f"  {s.name:<16} {s.inferred_type:<10} {val_repr:<18} {loc:<14}")

        lines.extend([
            "",
            "EVENTS:",
            f"  {'Name':<28} {'Location':<16}",
            f"  {'-'*28} {'-'*16}",
        ])

        if not self.events:
            lines.append("  (none)")
        else:
            for e in self.events.values():
                loc = f"Line {e.line}, Col {e.column}"
                lines.append(f"  {e.name:<28} {loc:<16}")

        lines.append("============================================================")
        return "\n".join(lines)
