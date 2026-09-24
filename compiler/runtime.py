"""
SEQUENT Compiler - Event-Driven Runtime & Temporal Monitoring
Provides deterministic event scheduling, temporal constraint verification,
and structured execution logging (CLI and JSON).
"""

from dataclasses import dataclass, field
import json
from typing import Any, Dict, List, Optional, Tuple

from compiler.bytecode import CompiledProgram
from compiler.vm import VirtualMachine, VMError


@dataclass
class TemporalCheckRecord:
    """Represents the runtime evaluation of a temporal constraint."""
    source_event: str
    target_event: str
    source_timestamp_ms: int
    target_timestamp_ms: Optional[int]
    elapsed_ms: Optional[int]
    limit_ms: int
    status: str  # "SATISFIED", "VIOLATED", "TIMEOUT"
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_event": self.source_event,
            "target_event": self.target_event,
            "source_timestamp_ms": self.source_timestamp_ms,
            "target_timestamp_ms": self.target_timestamp_ms,
            "elapsed_ms": self.elapsed_ms,
            "limit_ms": self.limit_ms,
            "status": self.status,
            "message": self.message,
        }


@dataclass
class EventDispatchRecord:
    """Log record for a single dispatched event."""
    event_name: str
    timestamp_ms: int
    handler_executed: bool
    state_changes: List[Dict[str, Any]] = field(default_factory=list)
    temporal_checks: List[TemporalCheckRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event": self.event_name,
            "timestamp_ms": self.timestamp_ms,
            "handler_executed": self.handler_executed,
            "state_changes": self.state_changes,
            "temporal_checks": [c.to_dict() for c in self.temporal_checks],
        }


@dataclass
class RuntimeExecutionResult:
    """Complete summary of a SEQUENT program runtime execution."""
    system_name: str
    initial_state: Dict[str, Any]
    final_state: Dict[str, Any]
    events_dispatched: List[EventDispatchRecord] = field(default_factory=list)
    temporal_evaluations: List[TemporalCheckRecord] = field(default_factory=list)
    total_events: int = 0
    total_state_changes: int = 0
    constraints_satisfied: int = 0
    constraints_violated: int = 0
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system": self.system_name,
            "initial_state": self.initial_state,
            "final_state": self.final_state,
            "events_dispatched": [e.to_dict() for e in self.events_dispatched],
            "temporal_evaluations": [t.to_dict() for t in self.temporal_evaluations],
            "summary": {
                "total_events": self.total_events,
                "total_state_changes": self.total_state_changes,
                "constraints_checked": len(self.temporal_evaluations),
                "constraints_satisfied": self.constraints_satisfied,
                "constraints_violated": self.constraints_violated,
                "success": self.success,
            },
        }

    def to_json(self, indent: int = 2) -> str:
        """Serializes the execution result into formatted JSON."""
        return json.dumps(self.to_dict(), indent=indent)


class TemporalRuntimeMonitor:
    """Monitors arrival times of events and verifies temporal constraints at runtime."""

    def __init__(self, constraints: List[Dict[str, Any]]):
        self.constraints = constraints
        # Map: event_name -> list of occurrence timestamps
        self.event_timestamps: Dict[str, List[int]] = {}
        # Records of evaluations performed
        self.evaluations: List[TemporalCheckRecord] = []
        # Active open expectations: source_event -> [(timestamp, constraint_dict)]
        self.open_expectations: Dict[str, List[Tuple[int, Dict[str, Any]]]] = {}

    def record_event(self, event_name: str, timestamp_ms: int) -> List[TemporalCheckRecord]:
        """Records an event occurrence and evaluates any matching temporal constraints."""
        new_checks: List[TemporalCheckRecord] = []

        if event_name not in self.event_timestamps:
            self.event_timestamps[event_name] = []
        self.event_timestamps[event_name].append(timestamp_ms)

        # 1. Check if this event fulfills any open expectations where event_name is the target
        for c in self.constraints:
            if c["target"] == event_name:
                src = c["source"]
                if src in self.open_expectations and self.open_expectations[src]:
                    # Pair with the earliest pending occurrence of the source event
                    src_time, _ = self.open_expectations[src].pop(0)
                    elapsed = timestamp_ms - src_time
                    limit = c["duration_ms"]
                    if elapsed <= limit:
                        record = TemporalCheckRecord(
                            source_event=src,
                            target_event=event_name,
                            source_timestamp_ms=src_time,
                            target_timestamp_ms=timestamp_ms,
                            elapsed_ms=elapsed,
                            limit_ms=limit,
                            status="SATISFIED",
                            message=f"TEMPORAL CONSTRAINT SATISFIED: {src} -> {event_name} elapsed {elapsed}ms <= limit {limit}ms",
                        )
                    else:
                        record = TemporalCheckRecord(
                            source_event=src,
                            target_event=event_name,
                            source_timestamp_ms=src_time,
                            target_timestamp_ms=timestamp_ms,
                            elapsed_ms=elapsed,
                            limit_ms=limit,
                            status="VIOLATED",
                            message=f"TEMPORAL CONSTRAINT VIOLATED: {src} -> {event_name} elapsed {elapsed}ms > limit {limit}ms",
                        )
                    self.evaluations.append(record)
                    new_checks.append(record)

        # 2. If this event is a source for any constraint, open an expectation
        for c in self.constraints:
            if c["source"] == event_name:
                if event_name not in self.open_expectations:
                    self.open_expectations[event_name] = []
                self.open_expectations[event_name].append((timestamp_ms, c))

        return new_checks

    def finalize(self) -> List[TemporalCheckRecord]:
        """Evaluates any lingering unfulfilled expectations at the end of execution."""
        timeout_checks: List[TemporalCheckRecord] = []
        for src, pending_list in self.open_expectations.items():
            for src_time, c in pending_list:
                record = TemporalCheckRecord(
                    source_event=src,
                    target_event=c["target"],
                    source_timestamp_ms=src_time,
                    target_timestamp_ms=None,
                    elapsed_ms=None,
                    limit_ms=c["duration_ms"],
                    status="TIMEOUT",
                    message=f"TEMPORAL CONSTRAINT VIOLATED (TIMEOUT): Target event '{c['target']}' did not occur after source '{src}'",
                )
                self.evaluations.append(record)
                timeout_checks.append(record)
        self.open_expectations.clear()
        return timeout_checks


class SequentRuntime:
    """Orchestrates VM execution, event dispatching, temporal monitoring, and execution logging."""

    def __init__(self, compiled_prog: CompiledProgram):
        self.program = compiled_prog
        self.vm = VirtualMachine(compiled_prog)
        self.monitor = TemporalRuntimeMonitor(compiled_prog.constraints)
        self.virtual_clock_ms: int = 0

    def run_simulation(self, event_timeline: List[Tuple[str, int]]) -> RuntimeExecutionResult:
        """Executes a simulation timeline: [(event_name, timestamp_ms), ...] sorted by timestamp."""
        self.vm.reset()
        self.monitor = TemporalRuntimeMonitor(self.program.constraints)
        self.virtual_clock_ms = 0

        initial_state = dict(self.vm.states)
        dispatch_records: List[EventDispatchRecord] = []
        total_state_changes = 0

        # Sort events deterministically by timestamp
        timeline = sorted(event_timeline, key=lambda x: x[1])

        for event_name, ts in timeline:
            self.virtual_clock_ms = ts

            # 1. Evaluate temporal constraints against this event arrival
            temporal_checks = self.monitor.record_event(event_name, ts)

            # 2. Execute handler in VM
            handler_exists = event_name in self.program.handler_table
            raw_changes = self.vm.execute_handler(event_name) if handler_exists else []

            # Format state changes
            formatted_changes: List[Dict[str, Any]] = []
            for var_name, old_val, new_val in raw_changes:
                formatted_changes.append({
                    "variable": var_name,
                    "old_value": old_val,
                    "new_value": new_val,
                })
                total_state_changes += 1

            record = EventDispatchRecord(
                event_name=event_name,
                timestamp_ms=ts,
                handler_executed=handler_exists,
                state_changes=formatted_changes,
                temporal_checks=temporal_checks,
            )
            dispatch_records.append(record)

        # Finalize temporal monitoring (checking timeouts)
        timeout_checks = self.monitor.finalize()
        if timeout_checks and dispatch_records:
            dispatch_records[-1].temporal_checks.extend(timeout_checks)

        # Count satisfaction / violations
        satisfied = sum(1 for c in self.monitor.evaluations if c.status == "SATISFIED")
        violated = sum(1 for c in self.monitor.evaluations if c.status in ("VIOLATED", "TIMEOUT"))

        return RuntimeExecutionResult(
            system_name=self.program.system_name,
            initial_state=initial_state,
            final_state=dict(self.vm.states),
            events_dispatched=dispatch_records,
            temporal_evaluations=list(self.monitor.evaluations),
            total_events=len(timeline),
            total_state_changes=total_state_changes,
            constraints_satisfied=satisfied,
            constraints_violated=violated,
            success=(violated == 0),
        )


def format_runtime_log(result: RuntimeExecutionResult) -> str:
    """Produces clean, formatted CLI execution output."""
    lines: List[str] = [
        "============================================================",
        "                    SEQUENT VM EXECUTION                    ",
        "============================================================",
        f"SEQUENT PROGRAM STARTED: {result.system_name}",
        "",
        "Initial State:",
    ]

    for k, v in result.initial_state.items():
        val_str = f'"{v}"' if isinstance(v, str) else str(v).lower() if isinstance(v, bool) else str(v)
        lines.append(f"  {k} = {val_str}")

    lines.append("")

    for rec in result.events_dispatched:
        lines.append("------------------------------------------------------------")
        lines.append(f"Event: {rec.event_name} at {rec.timestamp_ms} ms")
        if rec.handler_executed:
            lines.append(f"Handler: on {rec.event_name}")
            if rec.state_changes:
                lines.append("State Changes:")
                for sc in rec.state_changes:
                    old_str = f'"{sc["old_value"]}"' if isinstance(sc["old_value"], str) else str(sc["old_value"]).lower() if isinstance(sc["old_value"], bool) else str(sc["old_value"])
                    new_str = f'"{sc["new_value"]}"' if isinstance(sc["new_value"], str) else str(sc["new_value"]).lower() if isinstance(sc["new_value"], bool) else str(sc["new_value"])
                    lines.append(f"  {sc['variable']}: {old_str} -> {new_str}")
            else:
                lines.append("  (no state changes)")
        else:
            lines.append("  (no handler defined for this event)")

        for tc in rec.temporal_checks:
            lines.append("")
            lines.append("Temporal Constraint Check:")
            lines.append(f"  {tc.source_event} -> {tc.target_event}")
            lines.append(f"  Constraint Limit: {tc.limit_ms} ms")
            if tc.elapsed_ms is not None:
                lines.append(f"  Elapsed Time:     {tc.elapsed_ms} ms")
            if tc.status == "SATISFIED":
                lines.append("  Status:           TEMPORAL CONSTRAINT SATISFIED ✓")
            elif tc.status == "VIOLATED":
                lines.append("  Status:           TEMPORAL CONSTRAINT VIOLATED ✗")
            else:
                lines.append("  Status:           TEMPORAL CONSTRAINT TIMEOUT ✗")

    lines.extend([
        "",
        "============================================================",
        "PROGRAM EXECUTION COMPLETED",
        "============================================================",
        "Final State:",
    ])

    for k, v in result.final_state.items():
        val_str = f'"{v}"' if isinstance(v, str) else str(v).lower() if isinstance(v, bool) else str(v)
        lines.append(f"  {k} = {val_str}")

    lines.extend([
        "",
        f"Summary: {result.total_events} events dispatched, {result.total_state_changes} state changes, "
        f"{result.constraints_satisfied} temporal constraints satisfied, {result.constraints_violated} violated.",
        "============================================================",
    ])

    return "\n".join(lines)
