"""
SEQUENT Compiler - Abstract Syntax Tree (AST) Definitions
Defines AST nodes and an AST pretty-printer for the SEQUENT DSL.
"""

from dataclasses import dataclass, field
from typing import Any, List


class ASTNode:
    """Base class for all AST nodes."""
    line: int
    column: int


@dataclass
class LiteralNode(ASTNode):
    """Represents a literal value (int, float, string, bool)."""
    value: Any
    lit_type: str  # 'int', 'float', 'string', 'bool'
    line: int
    column: int

    def __repr__(self) -> str:
        val_str = f'"{self.value}"' if self.lit_type == "string" else str(self.value).lower() if self.lit_type == "bool" else str(self.value)
        return f"{val_str} [{self.lit_type}]"


@dataclass
class DurationNode(ASTNode):
    """Represents a time duration (e.g., 5s, 30m)."""
    amount: int
    unit: str  # 'ms', 's', 'm', 'h'
    line: int
    column: int

    def __repr__(self) -> str:
        return f"{self.amount}{self.unit}"


@dataclass
class StateDeclNode(ASTNode):
    """Represents a state declaration: state <name> = <literal>"""
    name: str
    initial_value: LiteralNode
    line: int
    column: int


@dataclass
class EventDeclNode(ASTNode):
    """Represents an event declaration: event <name>"""
    name: str
    line: int
    column: int


@dataclass
class AssignmentNode(ASTNode):
    """Represents a state assignment within a handler: <state> = <literal>"""
    state_name: str
    value: LiteralNode
    line: int
    column: int


@dataclass
class HandlerNode(ASTNode):
    """Represents an event handler: on <event> { <assignments> }"""
    event_name: str
    assignments: List[AssignmentNode] = field(default_factory=list)
    line: int = 1
    column: int = 1


@dataclass
class ConstraintNode(ASTNode):
    """Represents a temporal constraint: constraint <source> -> <target> within <duration>"""
    source_event: str
    target_event: str
    duration: DurationNode
    line: int = 1
    column: int = 1


@dataclass
class ProgramNode(ASTNode):
    """Root node of a SEQUENT program: system <name> { <body> }"""
    system_name: str
    declarations: List[ASTNode] = field(default_factory=list)  # StateDeclNode | EventDeclNode
    handlers: List[HandlerNode] = field(default_factory=list)
    constraints: List[ConstraintNode] = field(default_factory=list)
    line: int = 1
    column: int = 1


def format_ast(node: ASTNode) -> str:
    """Formats an AST into a readable tree-like string for CLI inspection."""
    if not isinstance(node, ProgramNode):
        return str(node)

    lines: List[str] = [f"Program: {node.system_name} (Line {node.line}, Col {node.column})"]

    # 1. Declarations branch
    dec_count = len(node.declarations)
    lines.append(f"├── Declarations ({dec_count})")
    for i, decl in enumerate(node.declarations):
        is_last_decl = (i == dec_count - 1)
        prefix = "│   └── " if is_last_decl else "│   ├── "
        if isinstance(decl, StateDeclNode):
            lines.append(f"{prefix}State: {decl.name} = {decl.initial_value} (Line {decl.line}, Col {decl.column})")
        elif isinstance(decl, EventDeclNode):
            lines.append(f"{prefix}Event: {decl.name} (Line {decl.line}, Col {decl.column})")

    # 2. Handlers branch
    h_count = len(node.handlers)
    lines.append(f"├── Handlers ({h_count})")
    for i, handler in enumerate(node.handlers):
        is_last_handler = (i == h_count - 1)
        h_prefix = "│   └── " if is_last_handler else "│   ├── "
        h_indent = "│       " if is_last_handler else "│   │   "
        lines.append(f"{h_prefix}Handler: on {handler.event_name} (Line {handler.line}, Col {handler.column})")
        a_count = len(handler.assignments)
        for j, assign in enumerate(handler.assignments):
            is_last_assign = (j == a_count - 1)
            a_prefix = "└── " if is_last_assign else "├── "
            lines.append(f"{h_indent}{a_prefix}Assignment: {assign.state_name} = {assign.value} (Line {assign.line}, Col {assign.column})")

    # 3. Constraints branch
    c_count = len(node.constraints)
    lines.append(f"└── Constraints ({c_count})")
    for i, c in enumerate(node.constraints):
        is_last_c = (i == c_count - 1)
        c_prefix = "    └── " if is_last_c else "    ├── "
        lines.append(f"{c_prefix}Constraint: {c.source_event} -> {c.target_event} within {c.duration} (Line {c.line}, Col {c.column})")

    return "\n".join(lines)
