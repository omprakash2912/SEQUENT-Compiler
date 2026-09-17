"""
SEQUENT Compiler - Semantic Analyzer
Performs static semantic checks including declaration uniqueness, scope resolution,
and literal type checking.
"""

from typing import Optional
from compiler.ast import ProgramNode, StateDeclNode, EventDeclNode
from compiler.symbol_table import SymbolTable


class SemanticError(Exception):
    """Exception raised for semantic errors during analysis."""

    def __init__(self, message: str, line: Optional[int] = None, column: Optional[int] = None):
        self.message = message
        self.line = line
        self.column = column
        loc = f" at line {line}, column {column}" if line is not None and column is not None else ""
        super().__init__(f"SEMANTIC ERROR: {message}{loc}")


class SemanticAnalyzer:
    """Performs semantic analysis and constructs the populated SymbolTable."""

    def __init__(self):
        self.symbol_table = SymbolTable()

    def analyze(self, program: ProgramNode) -> SymbolTable:
        """Analyzes the AST program. Returns the populated SymbolTable on success."""
        # 1. Process all declarations first to populate the symbol table
        for decl in program.declarations:
            if isinstance(decl, StateDeclNode):
                if self.symbol_table.has_state(decl.name):
                    raise SemanticError(f"Duplicate state declaration '{decl.name}'", decl.line, decl.column)
                if self.symbol_table.has_event(decl.name):
                    raise SemanticError(f"Identifier '{decl.name}' already declared as an event", decl.line, decl.column)

                inferred_type = decl.initial_value.lit_type
                initial_val = decl.initial_value.value
                self.symbol_table.define_state(
                    name=decl.name,
                    inferred_type=inferred_type,
                    initial_value=initial_val,
                    line=decl.line,
                    column=decl.column,
                )

            elif isinstance(decl, EventDeclNode):
                if self.symbol_table.has_event(decl.name):
                    raise SemanticError(f"Duplicate event declaration '{decl.name}'", decl.line, decl.column)
                if self.symbol_table.has_state(decl.name):
                    raise SemanticError(f"Identifier '{decl.name}' already declared as a state", decl.line, decl.column)

                self.symbol_table.define_event(
                    name=decl.name,
                    line=decl.line,
                    column=decl.column,
                )

        # 2. Validate all handlers and their assignments
        for handler in program.handlers:
            # Check handler event exists
            if not self.symbol_table.has_event(handler.event_name):
                if self.symbol_table.has_state(handler.event_name):
                    raise SemanticError(
                        f"Invalid handler event reference '{handler.event_name}'. '{handler.event_name}' is a state, not an event",
                        handler.line,
                        handler.column,
                    )
                raise SemanticError(
                    f"Undefined event '{handler.event_name}' in handler",
                    handler.line,
                    handler.column,
                )

            # Check assignments inside handler
            for assignment in handler.assignments:
                target_state = self.symbol_table.lookup_state(assignment.state_name)
                if target_state is None:
                    if self.symbol_table.has_event(assignment.state_name):
                        raise SemanticError(
                            f"Invalid assignment target '{assignment.state_name}'. Cannot assign to event '{assignment.state_name}'",
                            assignment.line,
                            assignment.column,
                        )
                    raise SemanticError(
                        f"Undefined state '{assignment.state_name}'",
                        assignment.line,
                        assignment.column,
                    )

                # Type checking
                expected_type = target_state.inferred_type
                actual_type = assignment.value.lit_type
                if expected_type != actual_type:
                    raise SemanticError(
                        f"Type mismatch for state '{assignment.state_name}'. Expected {expected_type} but got {actual_type}.",
                        assignment.line,
                        assignment.column,
                    )

        return self.symbol_table
