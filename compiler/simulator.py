"""
SEQUENT Compiler - Discrete-Event Simulation Engine
Provides a deterministic priority-queue discrete-event simulator for SEQUENT systems.
"""

from dataclasses import dataclass, field
import heapq
import json
from typing import Any, Dict, List, Optional, Tuple

from compiler.bytecode import CompiledProgram
from compiler.vm import VirtualMachine, VMError
from compiler.runtime import (
    TemporalRuntimeMonitor,
    TemporalCheckRecord,
    EventDispatchRecord,
)


@dataclass(order=True)
class SimulationEvent:
    """An event scheduled in the simulator's priority queue.

    Tie-breaking order:
    1. timestamp_ms (earliest first)
    2. priority (lower number = higher priority)
    3. seq_id (FIFO order of insertion)
    """
    timestamp_ms: int
    priority: int
    seq_id: int
    event_name: str = field(compare=False)
    payload: Any = field(default=None, compare=False)

    def __repr__(self) -> str:
        return f"SimulationEvent({self.event_name} @ {self.timestamp_ms}ms, prio={self.priority}, seq={self.seq_id})"


@dataclass
class SimulationResult:
    """Comprehensive execution trace and outcome of a discrete-event simulation."""
    system_name: str
    start_time_ms: int
    end_time_ms: int
    total_events_processed: int
    total_state_changes: int
    initial_state: Dict[str, Any]
    final_state: Dict[str, Any]
    events_log: List[Dict[str, Any]] = field(default_factory=list)
    state_transitions: List[Dict[str, Any]] = field(default_factory=list)
    temporal_evaluations: List[TemporalCheckRecord] = field(default_factory=list)
    constraints_satisfied: int = 0
    constraints_violated: int = 0
    constraints_timeout: int = 0
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Returns structured dictionary representation for telemetry and dashboard."""
        return {
            "system": self.system_name,
            "simulation": {
                "start_time_ms": self.start_time_ms,
                "end_time_ms": self.end_time_ms,
                "duration_ms": self.end_time_ms - self.start_time_ms,
                "total_events": self.total_events_processed,
                "total_state_changes": self.total_state_changes,
            },
            "initial_state": self.initial_state,
            "final_state": self.final_state,
            "events": self.events_log,
            "state_transitions": self.state_transitions,
            "temporal_checks": [t.to_dict() for t in self.temporal_evaluations],
            "summary": {
                "total_events": self.total_events_processed,
                "total_state_changes": self.total_state_changes,
                "constraints_checked": len(self.temporal_evaluations),
                "constraints_satisfied": self.constraints_satisfied,
                "constraints_violated": self.constraints_violated,
                "constraints_timeout": self.constraints_timeout,
                "success": self.success,
            },
        }

    def to_json(self, indent: int = 2) -> str:
        """Serializes the simulation result into standardized JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    def format_display(self) -> str:
        """Produces a clean terminal report of simulation outcomes."""
        lines = [
            "============================================================",
            "             SEQUENT DISCRETE-EVENT SIMULATION              ",
            "============================================================",
            f"SYSTEM: {self.system_name}",
            f"Simulation Clock Interval: {self.start_time_ms} ms -> {self.end_time_ms} ms ({self.end_time_ms - self.start_time_ms} ms total)",
            "",
            "Initial State:",
        ]
        for k, v in self.initial_state.items():
            val_str = f'"{v}"' if isinstance(v, str) else str(v).lower() if isinstance(v, bool) else str(v)
            lines.append(f"  {k} = {val_str}")

        lines.append("")
        for ev in self.events_log:
            lines.append("------------------------------------------------------------")
            lines.append(f"Event: {ev['event']} at {ev['timestamp_ms']} ms (priority: {ev['priority']})")
            if ev["handler_executed"]:
                lines.append(f"Handler: on {ev['event']}")
                if ev["state_changes"]:
                    lines.append("State Changes:")
                    for sc in ev["state_changes"]:
                        old_s = f'"{sc["old_value"]}"' if isinstance(sc["old_value"], str) else str(sc["old_value"]).lower() if isinstance(sc["old_value"], bool) else str(sc["old_value"])
                        new_s = f'"{sc["new_value"]}"' if isinstance(sc["new_value"], str) else str(sc["new_value"]).lower() if isinstance(sc["new_value"], bool) else str(sc["new_value"])
                        lines.append(f"  {sc['variable']}: {old_s} -> {new_s}")
                else:
                    lines.append("  (no state mutations)")
            else:
                lines.append("  (no handler defined for this event)")

            for tc in ev["temporal_checks"]:
                lines.append("")
                lines.append("Temporal Constraint Check:")
                lines.append(f"  {tc['source_event']} -> {tc['target_event']}")
                lines.append(f"  Constraint Limit: {tc['limit_ms']} ms")
                if tc["elapsed_ms"] is not None:
                    lines.append(f"  Elapsed Time:     {tc['elapsed_ms']} ms")
                status = tc["status"]
                if status == "SATISFIED":
                    lines.append("  Status:           TEMPORAL CONSTRAINT SATISFIED \u2713")
                elif status == "VIOLATED":
                    lines.append("  Status:           TEMPORAL CONSTRAINT VIOLATED \u2717")
                else:
                    lines.append("  Status:           TEMPORAL CONSTRAINT TIMEOUT \u2717")

        lines.extend([
            "",
            "============================================================",
            "SIMULATION COMPLETED",
            "============================================================",
            "Final State:",
        ])
        for k, v in self.final_state.items():
            val_str = f'"{v}"' if isinstance(v, str) else str(v).lower() if isinstance(v, bool) else str(v)
            lines.append(f"  {k} = {val_str}")

        lines.extend([
            "",
            f"Summary: {self.total_events_processed} events processed, {self.total_state_changes} state changes.",
            f"Constraints: {self.constraints_satisfied} satisfied, {self.constraints_violated} violated, {self.constraints_timeout} timeouts.",
            f"Overall Status: {'SUCCESS' if self.success else 'FAILED (Constraints Breached)'}",
            "============================================================",
        ])
        return "\n".join(lines)


class DiscreteEventSimulator:
    """Deterministic Priority-Queue Discrete-Event Simulator for SEQUENT programs."""

    def __init__(self, program: CompiledProgram):
        self.program = program
        self.vm = VirtualMachine(program)
        self.monitor = TemporalRuntimeMonitor(program.constraints)
        self.event_queue: List[SimulationEvent] = []
        self.seq_counter: int = 0
        self.virtual_clock_ms: int = 0

    def reset(self) -> None:
        """Resets the simulator, VM, and temporal monitor to initial conditions."""
        self.vm.reset()
        self.monitor = TemporalRuntimeMonitor(self.program.constraints)
        self.event_queue.clear()
        self.seq_counter = 0
        self.virtual_clock_ms = 0

    def schedule(self, event_name: str, timestamp_ms: int, priority: int = 10, payload: Any = None) -> SimulationEvent:
        """Schedules a new event in the priority queue.

        Args:
            event_name: The name of the event to dispatch.
            timestamp_ms: Arrival time in integer milliseconds (must be >= 0).
            priority: Priority integer (lower = higher priority, default = 10).
            payload: Optional payload passed to the event.
        """
        if timestamp_ms < 0:
            raise ValueError(f"Invalid timestamp '{timestamp_ms}ms': Event timestamps must be non-negative.")

        event = SimulationEvent(
            timestamp_ms=int(timestamp_ms),
            priority=int(priority),
            seq_id=self.seq_counter,
            event_name=event_name,
            payload=payload,
        )
        self.seq_counter += 1
        heapq.heappush(self.event_queue, event)
        return event

    def load_timeline(self, timeline: List[Tuple[str, int]]) -> None:
        """Schedules an entire list of (event_name, timestamp_ms) tuples into the queue."""
        for item in timeline:
            if len(item) == 2:
                name, ts = item
                self.schedule(name, ts)
            elif len(item) >= 3:
                name, ts, prio = item[0], item[1], item[2]
                self.schedule(name, ts, priority=prio)

    def run(self) -> SimulationResult:
        """Runs the discrete-event simulation until the event queue is empty."""
        initial_state = dict(self.vm.states)
        start_time_ms = self.event_queue[0].timestamp_ms if self.event_queue else 0
        events_log: List[Dict[str, Any]] = []
        state_transitions: List[Dict[str, Any]] = []
        total_state_changes = 0

        while self.event_queue:
            ev = heapq.heappop(self.event_queue)
            self.virtual_clock_ms = ev.timestamp_ms

            # 1. Temporal monitoring on event arrival
            new_checks = self.monitor.record_event(ev.event_name, ev.timestamp_ms)

            # 2. Execute handler in VM if registered
            handler_exists = ev.event_name in self.program.handler_table
            raw_changes = self.vm.execute_handler(ev.event_name) if handler_exists else []

            formatted_changes: List[Dict[str, Any]] = []
            for var_name, old_val, new_val in raw_changes:
                sc = {
                    "timestamp_ms": ev.timestamp_ms,
                    "event": ev.event_name,
                    "variable": var_name,
                    "old_value": old_val,
                    "new_value": new_val,
                }
                formatted_changes.append(sc)
                state_transitions.append(sc)
                total_state_changes += 1

            events_log.append({
                "event": ev.event_name,
                "timestamp_ms": ev.timestamp_ms,
                "priority": ev.priority,
                "seq_id": ev.seq_id,
                "handler_executed": handler_exists,
                "state_changes": formatted_changes,
                "temporal_checks": [c.to_dict() for c in new_checks],
            })

        # Finalize temporal expectations (timeouts)
        timeouts = self.monitor.finalize()
        if timeouts and events_log:
            events_log[-1]["temporal_checks"].extend([t.to_dict() for t in timeouts])

        satisfied = sum(1 for c in self.monitor.evaluations if c.status == "SATISFIED")
        violated = sum(1 for c in self.monitor.evaluations if c.status == "VIOLATED")
        timeout_count = sum(1 for c in self.monitor.evaluations if c.status == "TIMEOUT")
        has_failure = (violated > 0) or (timeout_count > 0)

        end_time_ms = self.virtual_clock_ms

        return SimulationResult(
            system_name=self.program.system_name,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            total_events_processed=len(events_log),
            total_state_changes=total_state_changes,
            initial_state=initial_state,
            final_state=dict(self.vm.states),
            events_log=events_log,
            state_transitions=state_transitions,
            temporal_evaluations=list(self.monitor.evaluations),
            constraints_satisfied=satisfied,
            constraints_violated=violated,
            constraints_timeout=timeout_count,
            success=(not has_failure),
        )
