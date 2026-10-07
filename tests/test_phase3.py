"""
SEQUENT Compiler - Phase 3 Comprehensive Test Suite
Deterministic unit and integration tests covering:
- Discrete-Event Simulation Engine (heapq priority queue, tie-breaking, virtual clock)
- Runtime Temporal Monitoring (Satisfied, Exact Boundary, Violated, Timeout)
- Binary Bytecode Serialization (.seqc, CRC32 integrity, corrupted header/payload errors)
- Execution equivalence: Source -> VM vs. Source -> .seqc -> VM
- Telemetry JSON schema compliance for the Web Dashboard
- Performance benchmark execution
- End-to-end simulation of Phase 3 example programs
"""

import json
from pathlib import Path
import tempfile
import unittest

from compiler import compile_source, simulate_source
from compiler.bytecode import BytecodeGenerator, CompiledProgram, OpCode, BytecodeInstruction
from compiler.simulator import DiscreteEventSimulator, SimulationEvent, SimulationResult
from compiler.serializer import (
    BytecodeSerializer,
    SerializationError,
    serialize_program,
    deserialize_program,
    save_seqc,
    load_seqc,
)
from compiler.benchmark import run_benchmark


class TestDiscreteEventSimulator(unittest.TestCase):
    """Unit tests for the Priority-Queue Discrete-Event Simulator."""

    def setUp(self):
        source = """
        system SimTestSystem {
            state count = 0
            state status = "IDLE"
            event EvA
            event EvB
            event EvC
            on EvA {
                count = 1
                status = "RUNNING"
            }
            on EvB {
                count = 2
            }
            on EvC {
                status = "DONE"
            }
            constraint EvA -> EvC within 5s
        }
        """
        c_res = compile_source(source)
        self.assertTrue(c_res.success)
        self.program = c_res.bytecode

    def test_empty_queue(self):
        sim = DiscreteEventSimulator(self.program)
        res = sim.run()
        self.assertEqual(res.total_events_processed, 0)
        self.assertEqual(res.total_state_changes, 0)
        self.assertEqual(res.initial_state["count"], 0)
        self.assertEqual(res.final_state["count"], 0)
        self.assertTrue(res.success)

    def test_single_event(self):
        sim = DiscreteEventSimulator(self.program)
        sim.schedule("EvA", timestamp_ms=500)
        res = sim.run()
        self.assertEqual(res.total_events_processed, 1)
        self.assertEqual(res.final_state["count"], 1)
        self.assertEqual(res.final_state["status"], "RUNNING")
        self.assertEqual(res.start_time_ms, 500)
        self.assertEqual(res.end_time_ms, 500)

    def test_timestamp_ordering(self):
        # Insert out of chronological order: 3000ms, then 500ms, then 1500ms
        sim = DiscreteEventSimulator(self.program)
        sim.schedule("EvC", timestamp_ms=3000)
        sim.schedule("EvA", timestamp_ms=500)
        sim.schedule("EvB", timestamp_ms=1500)
        res = sim.run()

        processed_order = [e["event"] for e in res.events_log]
        self.assertEqual(processed_order, ["EvA", "EvB", "EvC"])
        timestamps = [e["timestamp_ms"] for e in res.events_log]
        self.assertEqual(timestamps, [500, 1500, 3000])

    def test_same_timestamp_priority_tie_breaking(self):
        # Events at same timestamp (1000ms): lower priority integer runs first
        sim = DiscreteEventSimulator(self.program)
        sim.schedule("EvB", timestamp_ms=1000, priority=20)
        sim.schedule("EvA", timestamp_ms=1000, priority=5)  # Priority 5 should pop before 20
        res = sim.run()

        self.assertEqual(res.events_log[0]["event"], "EvA")
        self.assertEqual(res.events_log[1]["event"], "EvB")

    def test_same_timestamp_fifo_tie_breaking(self):
        # Same timestamp and same priority: insertion order (seq_id) determines order
        sim = DiscreteEventSimulator(self.program)
        sim.schedule("EvA", timestamp_ms=1000, priority=10)
        sim.schedule("EvB", timestamp_ms=1000, priority=10)
        res = sim.run()

        self.assertEqual(res.events_log[0]["event"], "EvA")
        self.assertEqual(res.events_log[1]["event"], "EvB")

    def test_negative_timestamp_error(self):
        sim = DiscreteEventSimulator(self.program)
        with self.assertRaises(ValueError) as ctx:
            sim.schedule("EvA", timestamp_ms=-100)
        self.assertIn("non-negative", str(ctx.exception).lower())

    def test_state_transitions_history(self):
        sim = DiscreteEventSimulator(self.program)
        sim.schedule("EvA", timestamp_ms=100)
        res = sim.run()
        self.assertTrue(len(res.state_transitions) >= 2)
        vars_mutated = [st["variable"] for st in res.state_transitions]
        self.assertIn("count", vars_mutated)
        self.assertIn("status", vars_mutated)


class TestTemporalMonitoringPhase3(unittest.TestCase):
    """Unit tests for Phase 3 Temporal Runtime Monitoring improvements."""

    def setUp(self):
        source = """
        system TimingTest {
            event Start
            event Stop
            constraint Start -> Stop within 2s
        }
        """
        c_res = compile_source(source)
        self.program = c_res.bytecode

    def test_temporal_satisfied(self):
        sim = DiscreteEventSimulator(self.program)
        sim.schedule("Start", 0)
        sim.schedule("Stop", 1500)  # 1500ms <= 2000ms
        res = sim.run()
        self.assertEqual(res.constraints_satisfied, 1)
        self.assertEqual(res.constraints_violated, 0)
        self.assertEqual(res.constraints_timeout, 0)
        self.assertTrue(res.success)
        self.assertEqual(res.temporal_evaluations[0].status, "SATISFIED")
        self.assertEqual(res.temporal_evaluations[0].elapsed_ms, 1500)

    def test_temporal_exact_boundary_satisfied(self):
        sim = DiscreteEventSimulator(self.program)
        sim.schedule("Start", 1000)
        sim.schedule("Stop", 3000)  # Exactly 2000ms == 2000ms limit
        res = sim.run()
        self.assertEqual(res.constraints_satisfied, 1)
        self.assertEqual(res.constraints_violated, 0)
        self.assertTrue(res.success)
        self.assertEqual(res.temporal_evaluations[0].status, "SATISFIED")
        self.assertEqual(res.temporal_evaluations[0].elapsed_ms, 2000)

    def test_temporal_violated(self):
        sim = DiscreteEventSimulator(self.program)
        sim.schedule("Start", 0)
        sim.schedule("Stop", 2500)  # 2500ms > 2000ms limit
        res = sim.run()
        self.assertEqual(res.constraints_satisfied, 0)
        self.assertEqual(res.constraints_violated, 1)
        self.assertFalse(res.success)
        self.assertEqual(res.temporal_evaluations[0].status, "VIOLATED")
        self.assertEqual(res.temporal_evaluations[0].elapsed_ms, 2500)

    def test_temporal_timeout(self):
        sim = DiscreteEventSimulator(self.program)
        sim.schedule("Start", 0)
        # Stop never dispatched
        res = sim.run()
        self.assertEqual(res.constraints_satisfied, 0)
        self.assertEqual(res.constraints_timeout, 1)
        self.assertFalse(res.success)
        self.assertEqual(res.temporal_evaluations[0].status, "TIMEOUT")
        self.assertEqual(res.temporal_evaluations[0].source_event, "Start")
        self.assertEqual(res.temporal_evaluations[0].target_event, "Stop")


class TestBytecodeSerialization(unittest.TestCase):
    """Unit tests for binary .seqc serialization and integrity verification."""

    def setUp(self):
        source = """
        system SerTest {
            state x = 42
            state flag = true
            state tag = "ALPHA"
            event Trigger
            event Ack
            on Trigger {
                x = 100
                flag = false
                tag = "BETA"
            }
            constraint Trigger -> Ack within 5s
        }
        """
        c_res = compile_source(source)
        self.assertTrue(c_res.success)
        self.program = c_res.bytecode

    def test_serialization_roundtrip_equality(self):
        data = serialize_program(self.program)
        self.assertTrue(data.startswith(b"SEQC"))
        deserialized = deserialize_program(data)

        self.assertEqual(deserialized.system_name, self.program.system_name)
        self.assertEqual(deserialized.initial_states, self.program.initial_states)
        self.assertEqual(deserialized.state_types, self.program.state_types)
        self.assertEqual(deserialized.events, self.program.events)
        self.assertEqual(len(deserialized.instructions), len(self.program.instructions))
        self.assertEqual(deserialized.handler_table, self.program.handler_table)

    def test_serialized_execution_equivalence(self):
        # Direct simulation on original bytecode
        sim_orig = DiscreteEventSimulator(self.program)
        sim_orig.schedule("Trigger", 0)
        sim_orig.schedule("Ack", 1000)
        res_orig = sim_orig.run()

        # Simulation on serialized & deserialized bytecode
        data = serialize_program(self.program)
        deserialized = deserialize_program(data)
        sim_deser = DiscreteEventSimulator(deserialized)
        sim_deser.schedule("Trigger", 0)
        sim_deser.schedule("Ack", 1000)
        res_deser = sim_deser.run()

        self.assertEqual(res_orig.final_state, res_deser.final_state)
        self.assertEqual(res_orig.constraints_satisfied, res_deser.constraints_satisfied)
        self.assertEqual(res_orig.success, res_deser.success)

    def test_invalid_magic_header(self):
        data = bytearray(serialize_program(self.program))
        data[0:4] = b"BADM"
        with self.assertRaises(SerializationError) as ctx:
            deserialize_program(bytes(data))
        self.assertIn("magic header", str(ctx.exception).lower())

    def test_unsupported_version(self):
        data = bytearray(serialize_program(self.program))
        # Modify version from 1 to 99 (bytes 4-5)
        data[4] = 0
        data[5] = 99
        # Update CRC to pass CRC check and test version check
        with self.assertRaises(SerializationError) as ctx:
            deserialize_program(bytes(data))
        self.assertIn("version", str(ctx.exception).lower())

    def test_truncated_header(self):
        with self.assertRaises(SerializationError) as ctx:
            deserialize_program(b"SEQC")  # Less than 16 bytes
        self.assertIn("truncated", str(ctx.exception).lower())

    def test_truncated_payload(self):
        data = serialize_program(self.program)
        truncated = data[:len(data) - 10]
        with self.assertRaises(SerializationError) as ctx:
            deserialize_program(truncated)
        self.assertIn("truncated", str(ctx.exception).lower())

    def test_crc32_checksum_mismatch(self):
        data = bytearray(serialize_program(self.program))
        # Corrupt a byte in the payload area
        data[-1] = (data[-1] + 1) % 256
        with self.assertRaises(SerializationError) as ctx:
            deserialize_program(bytes(data))
        self.assertIn("crc32 checksum mismatch", str(ctx.exception).lower())

    def test_save_and_load_seqc_file(self):
        with tempfile.NamedTemporaryFile(suffix=".seqc", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            bytes_written = save_seqc(self.program, tmp_path)
            self.assertTrue(bytes_written > 16)
            loaded = load_seqc(tmp_path)
            self.assertEqual(loaded.system_name, self.program.system_name)
            self.assertEqual(len(loaded.instructions), len(self.program.instructions))
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestDashboardTelemetrySchema(unittest.TestCase):
    """Unit tests validating JSON telemetry output schema for the dashboard."""

    def test_telemetry_json_schema(self):
        source = """
        system TelemetryTest {
            state x = 1
            event Ev
            on Ev { x = 2 }
        }
        """
        c_res, sim_res = simulate_source(source, [("Ev", 100)])
        self.assertTrue(c_res.success)
        data = sim_res.to_dict()

        # Check required root fields
        required_roots = ["system", "simulation", "initial_state", "final_state", "events", "state_transitions", "temporal_checks", "summary"]
        for key in required_roots:
            self.assertIn(key, data, f"Missing root key '{key}' in telemetry JSON")

        # Check simulation block
        self.assertIn("start_time_ms", data["simulation"])
        self.assertIn("end_time_ms", data["simulation"])
        self.assertIn("duration_ms", data["simulation"])

        # Check summary block
        self.assertIn("total_events", data["summary"])
        self.assertIn("total_state_changes", data["summary"])
        self.assertIn("constraints_satisfied", data["summary"])
        self.assertIn("constraints_violated", data["summary"])
        self.assertIn("success", data["summary"])


class TestBenchmark(unittest.TestCase):
    """Unit tests for the performance benchmark suite."""

    def test_benchmark_execution(self):
        source = "system BenchSys { state x = 0 event E on E { x = 1 } }"
        res = run_benchmark(source, compilation_rounds=10)
        self.assertTrue(res.compilation_iterations == 10)
        self.assertTrue(res.compiles_per_sec > 0)
        self.assertTrue(res.sim_1000_events_per_sec > 0)
        display = res.format_display()
        self.assertIn("SEQUENT PERFORMANCE BENCHMARK REPORT", display)


class TestPhase3EndToEndExamples(unittest.TestCase):
    """Integration tests running all Phase 3 example programs."""

    def test_phase3_simulation_example(self):
        path = Path("examples/phase3_simulation.seq")
        source = path.read_text(encoding="utf-8")
        c_res, res = simulate_source(source)
        self.assertTrue(c_res.success)
        self.assertIsNotNone(res)
        self.assertEqual(res.constraints_satisfied, 2)
        self.assertEqual(res.constraints_violated, 0)
        self.assertEqual(res.constraints_timeout, 0)
        self.assertTrue(res.success)

    def test_phase3_timeout_example(self):
        path = Path("examples/phase3_timeout.seq")
        source = path.read_text(encoding="utf-8")
        c_res, res = simulate_source(source)
        self.assertTrue(c_res.success)
        self.assertIsNotNone(res)
        self.assertEqual(res.constraints_satisfied, 1)
        self.assertEqual(res.constraints_timeout, 1)
        self.assertFalse(res.success)

    def test_phase3_complex_example(self):
        path = Path("examples/phase3_complex.seq")
        source = path.read_text(encoding="utf-8")
        c_res, res = simulate_source(source)
        self.assertTrue(c_res.success)
        self.assertIsNotNone(res)
        self.assertEqual(res.constraints_satisfied, 3)
        self.assertEqual(res.constraints_violated, 0)
        self.assertTrue(res.success)


if __name__ == "__main__":
    unittest.main()
