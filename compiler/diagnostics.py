"""
SEQUENT Compiler - Structured Diagnostics & Rule-Based Assistant Module
Provides VS Code-style diagnostic models, error explanations, actionable suggestions,
and non-destructive fix generation for the SEQUENT DSL.
"""

from dataclasses import dataclass
import difflib
import re
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CompilerDiagnostic:
    """Structured compiler diagnostic representation (VS Code style)."""
    stage: str                  # "LEXER", "PARSER", "SEMANTIC", "TEMPORAL", "VERIFICATION", "RUNTIME"
    severity: str               # "ERROR", "WARNING", "INFO"
    line: Optional[int]         # 1-based line number
    column: Optional[int]       # 1-based column number
    end_column: Optional[int]   # 1-based end column
    message: str                # Human-readable compiler error message
    explanation: str            # Rule-based beginner-friendly explanation
    suggestion: str             # Actionable suggestion for the user
    token: Optional[str] = None # Relevant token or identifier if extracted
    token_column: Optional[int] = None
    token_end_column: Optional[int] = None
    code_fix: Optional[Dict[str, Any]] = None  # Optional automatic fix proposal
    declared_events: Optional[List[str]] = None
    declared_states: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "stage": self.stage,
            "severity": self.severity,
            "line": self.line,
            "column": self.column,
            "end_column": self.end_column,
            "message": self.message,
            "explanation": self.explanation,
            "suggestion": self.suggestion,
        }
        if self.token is not None:
            d["token"] = self.token
        if self.token_column is not None:
            d["token_column"] = self.token_column
        if self.token_end_column is not None:
            d["token_end_column"] = self.token_end_column
        if self.code_fix is not None:
            d["code_fix"] = self.code_fix
        if self.declared_events is not None:
            d["declared_events"] = self.declared_events
        if self.declared_states is not None:
            d["declared_states"] = self.declared_states
        return d


def extract_quoted_token(message: str) -> Optional[str]:
    """Extracts quoted identifier or token from error message (e.g. 'UnknownEvent')."""
    match = re.search(r"'([^']+)'", message)
    if match:
        return match.group(1)
    return None


def find_closest_symbol(token: Optional[str], candidates: Optional[List[str]]) -> Optional[str]:
    """Finds the closest candidate symbol using string similarity matching."""
    if not token or not candidates:
        return None
    matches = difflib.get_close_matches(token, candidates, n=1, cutoff=0.55)
    if matches:
        return matches[0]
    scored = sorted(
        candidates,
        key=lambda c: difflib.SequenceMatcher(None, token.lower(), c.lower()).ratio(),
        reverse=True,
    )
    return scored[0] if scored else None


def calculate_column_span(
    source_code: str,
    line: Optional[int],
    column: Optional[int],
    token: Optional[str] = None,
) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
    """Calculates column, end_column, and token-level start/end columns on source line.
    
    Returns: (column, end_column, token_column, token_end_column)
    """
    if line is None or not source_code:
        return column, None, None, None

    lines = source_code.splitlines()
    if not (1 <= line <= len(lines)):
        return column, None, None, None

    line_text = lines[line - 1]
    token_col = None
    token_end_col = None

    if token:
        idx = line_text.find(token)
        if idx != -1:
            token_col = idx + 1
            token_end_col = token_col + len(token)

    # Calculate end_column
    end_col = None
    if column is not None:
        if token_col is not None and column == token_col:
            end_col = token_end_col
        else:
            remaining = line_text[column - 1 :] if column <= len(line_text) + 1 else ""
            word_match = re.match(r"[A-Za-z0-9_]+", remaining)
            if word_match:
                end_col = column + len(word_match.group(0))
            else:
                end_col = column + 1

    return column, end_col, token_col, token_end_col


def create_diagnostic_from_error(
    stage: str,
    error_message: str,
    line: Optional[int] = None,
    column: Optional[int] = None,
    source_code: str = "",
    symbol_table: Any = None,
    ast: Any = None,
    category: str = "ERROR",
) -> CompilerDiagnostic:
    """Builds a rich CompilerDiagnostic from error details and AST/SymbolTable context."""
    token = extract_quoted_token(error_message)
    col, end_col, tok_col, tok_end_col = calculate_column_span(source_code, line, column, token)

    # Collect declared events and states if available
    declared_events: List[str] = []
    declared_states: List[str] = []
    if symbol_table is not None:
        if hasattr(symbol_table, "events"):
            declared_events = list(symbol_table.events.keys())
        if hasattr(symbol_table, "states"):
            declared_states = list(symbol_table.states.keys())
    elif ast is not None and hasattr(ast, "declarations"):
        from compiler.ast import StateDeclNode, EventDeclNode
        for d in ast.declarations:
            if isinstance(d, EventDeclNode):
                declared_events.append(d.name)
            elif isinstance(d, StateDeclNode):
                declared_states.append(d.name)

    explanation = ""
    suggestion = ""
    code_fix: Optional[Dict[str, Any]] = None

    stage_upper = stage.upper()
    msg_lower = error_message.lower()

    if stage_upper == "TEMPORAL":
        if "undefined event" in msg_lower or "undeclared event" in msg_lower or "not declared" in msg_lower:
            explanation = "The target event must be declared before it is used."
            closest = find_closest_symbol(token, declared_events)
            if closest:
                suggestion = f"Did you mean '{closest}'? Replace '{token}' with '{closest}'."
                code_fix = {
                    "type": "replace_token",
                    "target": token,
                    "replacement": closest,
                    "line": line,
                    "column": tok_col or col,
                }
            else:
                suggestion = f"Declare 'event {token}' in the system declaration or use an existing event."
        elif "non-positive duration" in msg_lower or "duration must be strictly positive" in msg_lower:
            explanation = "Duration must be positive. Valid examples include 5s, 500ms, 30m."
            suggestion = "Specify a positive duration such as 500ms, 5s, 30m, or 1h."
        elif "invalid duration unit" in msg_lower:
            explanation = "The duration unit is unrecognized. SEQUENT requires strict physical time units."
            suggestion = "Supported duration units are 'ms' (milliseconds), 's' (seconds), 'm' (minutes), or 'h' (hours)."
        else:
            explanation = "The temporal constraint refers to an event that is not declared or contains an invalid duration."
            suggestion = "Check constraint format: 'constraint <SourceEvent> -> <TargetEvent> within <Duration>'."

    elif stage_upper == "SEMANTIC":
        if "undefined state" in msg_lower:
            explanation = "This identifier is being used but was not declared or is incompatible with the expected type."
            closest = find_closest_symbol(token, declared_states)
            if closest:
                suggestion = f"Did you mean state '{closest}'? Replace '{token}' with '{closest}'."
                code_fix = {
                    "type": "replace_token",
                    "target": token,
                    "replacement": closest,
                    "line": line,
                    "column": tok_col or col,
                }
            else:
                suggestion = f"Declare state '{token}' with an initial value, e.g., 'state {token} = false'."
        elif "undefined event" in msg_lower or "undeclared event" in msg_lower:
            explanation = "This identifier is being used but was not declared or is incompatible with the expected type."
            closest = find_closest_symbol(token, declared_events)
            if closest:
                suggestion = f"Did you mean event '{closest}'? Replace '{token}' with '{closest}'."
                code_fix = {
                    "type": "replace_token",
                    "target": token,
                    "replacement": closest,
                    "line": line,
                    "column": tok_col or col,
                }
            else:
                suggestion = f"Declare 'event {token}' in the system declaration before attaching a handler."
        elif "type mismatch" in msg_lower:
            explanation = f"Type mismatch: The assigned value does not match the static inferred type of state '{token}'."
            suggestion = f"Assign a literal matching the initial declaration type of state '{token}'."
        elif "duplicate state" in msg_lower:
            explanation = f"State variable '{token}' is declared multiple times. State names must be unique."
            suggestion = f"Remove the duplicate declaration or rename one of the '{token}' state variables."
        elif "duplicate event" in msg_lower:
            explanation = f"Event '{token}' is declared multiple times. Event names must be unique."
            suggestion = f"Remove the duplicate declaration of event '{token}'."
        elif "already declared as an event" in msg_lower:
            explanation = f"Identifier '{token}' was already declared as an event and cannot also be a state variable."
            suggestion = "Use distinct names for events and state variables."
        else:
            explanation = "This identifier is being used but was not declared or is incompatible with the expected type."
            suggestion = "Verify all state and event identifiers and their types."

    elif stage_upper == "PARSER":
        if "expected '}'" in msg_lower:
            explanation = "The compiler could not understand this statement. Check the keyword, braces, operators, or statement structure."
            suggestion = "Add a closing brace '}' at the end of the unclosed handler or system block."
            code_fix = {
                "type": "append_text",
                "replacement": "\n}",
                "line": line,
                "column": col or 1,
            }
        elif "expected 'system'" in msg_lower:
            explanation = "The compiler could not understand this statement. Check the keyword, braces, operators, or statement structure."
            suggestion = "Begin your program with 'system <SystemName> {'."
        else:
            explanation = "The compiler could not understand this statement. Check the keyword, braces, operators, or statement structure."
            suggestion = f"Check statement structure around line {line or 1}, column {column or 1}."

    elif stage_upper == "LEXER":
        if "unexpected character" in msg_lower:
            ch = token if token else ""
            explanation = f"The character '{ch}' is not a valid token in the SEQUENT DSL grammar."
            suggestion = f"Remove or replace the unrecognized character '{ch}'."
        elif "unterminated string" in msg_lower:
            explanation = "A string literal was opened with a quotation mark but never closed before end of line."
            suggestion = "Add a closing quotation mark '\"' to terminate the string literal."
        else:
            explanation = "A lexical tokenization error occurred while scanning source code."
            suggestion = "Check for invalid characters or unterminated literals."

    elif stage_upper in ("VERIFICATION", "RUNTIME"):
        explanation = "A runtime temporal constraint was violated during discrete-event simulation."
        suggestion = "Review the event timestamps in the simulation timeline or adjust the deadline."

    else:
        explanation = "A compiler error occurred during execution."
        suggestion = "Review the source code and try compiling again."

    return CompilerDiagnostic(
        stage=stage_upper,
        severity="ERROR",
        line=line,
        column=col,
        end_column=end_col,
        message=error_message,
        explanation=explanation,
        suggestion=suggestion,
        token=token,
        token_column=tok_col,
        token_end_column=tok_end_col,
        code_fix=code_fix,
        declared_events=declared_events if declared_events else None,
        declared_states=declared_states if declared_states else None,
    )


TEMPLATES: Dict[str, Dict[str, str]] = {
    "emergency_response": {
        "id": "emergency_response",
        "name": "Emergency Response",
        "description": "Standard emergency dispatch coordinator with 5s and 30m response deadlines.",
        "default_events": "EmergencyDetected@0ms, TeamDispatched@3200ms, IncidentResolved@5000ms",
        "code": """system EmergencyResponseSystem {

    state active = false
    state team = "AVAILABLE"

    event EmergencyDetected
    event TeamDispatched
    event IncidentResolved

    constraint EmergencyDetected -> TeamDispatched within 5s
    constraint TeamDispatched -> IncidentResolved within 30m

    on EmergencyDetected {
        active = true
        team = "DISPATCHED"
    }

    on TeamDispatched {
        team = "EN_ROUTE"
    }

    on IncidentResolved {
        active = false
        team = "AVAILABLE"
    }
}
""",
    },
    "industrial_monitoring": {
        "id": "industrial_monitoring",
        "name": "Industrial Monitoring",
        "description": "Pressure safety system with automatic relief valve and stabilization monitoring.",
        "default_events": "PressureThresholdExceeded@0ms, ReliefValveTriggered@1200ms, PressureStabilized@4500ms",
        "code": """system IndustrialMonitoringSystem {

    state pressure_alert = false
    state valve_open = false
    state safe_mode = false

    event PressureThresholdExceeded
    event ReliefValveTriggered
    event PressureStabilized

    constraint PressureThresholdExceeded -> ReliefValveTriggered within 2000ms
    constraint ReliefValveTriggered -> PressureStabilized within 10s

    on PressureThresholdExceeded {
        pressure_alert = true
        safe_mode = true
    }

    on ReliefValveTriggered {
        valve_open = true
    }

    on PressureStabilized {
        pressure_alert = false
        valve_open = false
        safe_mode = false
    }
}
""",
    },
    "smart_building": {
        "id": "smart_building",
        "name": "Smart Building",
        "description": "Building power grid failover with auxiliary generator and grid restoration.",
        "default_events": "PowerGridFailure@0ms, AuxGeneratorStarted@1800ms, GridRestored@5000ms",
        "code": """system SmartBuildingSystem {

    state power_alert = false
    state auxiliary_power = false
    state grid_stable = true

    event PowerGridFailure
    event AuxGeneratorStarted
    event GridRestored

    constraint PowerGridFailure -> AuxGeneratorStarted within 3s
    constraint AuxGeneratorStarted -> GridRestored within 1h

    on PowerGridFailure {
        power_alert = true
        grid_stable = false
    }

    on AuxGeneratorStarted {
        auxiliary_power = true
    }

    on GridRestored {
        power_alert = false
        auxiliary_power = false
        grid_stable = true
    }
}
""",
    },
    "simple_timer": {
        "id": "simple_timer",
        "name": "Simple Timer",
        "description": "Discrete timer loop with periodic tick verification and expiration handler.",
        "default_events": "StartTimer@0ms, TimerTick@800ms, TimerExpired@3500ms",
        "code": """system SimpleTimerSystem {

    state timer_running = false
    state ticks = 0

    event StartTimer
    event TimerTick
    event TimerExpired

    constraint StartTimer -> TimerTick within 1s
    constraint TimerTick -> TimerExpired within 5s

    on StartTimer {
        timer_running = true
        ticks = 1
    }

    on TimerTick {
        ticks = 2
    }

    on TimerExpired {
        timer_running = false
        ticks = 0
    }
}
""",
    },
    "fault_detection": {
        "id": "fault_detection",
        "name": "Fault Detection",
        "description": "Critical sensor fault detection, failsafe engagement, and diagnostic recovery.",
        "default_events": "SensorFaultDetected@0ms, FailsafeEngaged@350ms, DiagnosticsCompleted@8000ms",
        "code": """system FaultDetectionSystem {

    state fault_active = false
    state safe_mode = false
    state alert_level = 0

    event SensorFaultDetected
    event FailsafeEngaged
    event DiagnosticsCompleted

    constraint SensorFaultDetected -> FailsafeEngaged within 500ms
    constraint FailsafeEngaged -> DiagnosticsCompleted within 15s

    on SensorFaultDetected {
        fault_active = true
        safe_mode = true
        alert_level = 1
    }

    on FailsafeEngaged {
        alert_level = 2
    }

    on DiagnosticsCompleted {
        fault_active = false
        safe_mode = false
        alert_level = 0
    }
}
""",
    },
}