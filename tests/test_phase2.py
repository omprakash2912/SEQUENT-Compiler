"""
SEQUENT Compiler - Phase 2 Comprehensive Test Suite
Deterministic unit and integration tests covering:
- AST -> IR generation
- IR structure and instruction formats
- IR dead-store and redundant assignment optimization
- Bytecode generation and instruction disassembly
- Stack-based Virtual Machine execution
- Event-driven handler dispatching and state mutations
- Runtime temporal constraint monitoring (Satisfied, Violated, Timeout)
- Execution logging and JSON serialization
- Edge cases: Stack underflow, unknown state, empty timelines, multi-handler optimization
- End-to-end execution of Phase 2 example programs
"""

import json
import unittest
from pathlib import Path

from compiler import compile_source, execute_source, parse_timeline_string
from compiler.ir import IRGenerator, IROpCode, format_ir
from compiler.ir_optimizer import IROptimizer, format_optimization_comparison
from compiler.bytecode import BytecodeGenerator, BytecodeInstruction, OpCode, format_bytecode
from compiler.vm import VirtualMachine, VMError
from compiler.runtime import SequentRuntime, TemporalRuntimeMonitor


class TestIRGeneration(unittest.TestCase):
    """Unit tests for AST -> Intermediate Representation generation."""

    def test_ir_generation_states_and_events(self):
        source = """
        system TestSystem {
            state count = 10
            state flag = true
            state label = "ONLINE"
            event SigA
            event SigB
            on SigA {
                count = 20
                flag = false
            }
            constraint SigA -> SigB within 5s
        }
        """
        c_res = compile_source(source)
        self.assertTrue(c_res.success)
        self.assertIsNotNone(c_res.ir)
        ir = c_res.ir

        self.assertEqual(ir.system_name, "TestSystem")
        self.assertIn("count", ir.states)
        self.assertEqual(ir.states["count"].initial_value, 10)
        self.assertEqual(ir.states["count"].inferred_type, "int")
        self.assertIn("flag", ir.states)
        self.assertEqual(ir.states["flag"].initial_value, True)
        self.assertIn("label", ir.states)
        self.assertEqual(ir.states["label"].initial_value, "ONLINE")

        self.assertEqual(ir.events, ["SigA", "SigB"])
        self.assertEqual(len(ir.constraints), 1)
        self.assertEqual(ir.constraints[0].duration_ms, 5000)

        # Instructions check
        opcodes = [inst.opcode for inst in ir.instructions]
        self.assertIn(IROpCode.LABEL_HANDLER, opcodes)
        self.assertIn(IROpCode.STORE_STATE, opcodes)
        self.assertIn(IROpCode.END_HANDLER, opcodes)

    def test_ir_multiple_constraints(self):
        source = """
        system MultiConstraint {
            event E1
            event E2
            event E3
            event E4
            constraint E1 -> E2 within 250ms
            constraint E2 -> E3 within 10s
            constraint E3 -> E4 within 1h
        }
        """
        c_res = compile_source(source)
        self.assertTrue(c_res.success)
        ir = c_res.ir
        self.assertEqual(len(ir.constraints), 3)
        self.assertEqual(ir.constraints[0].duration_ms, 250)
        self.assertEqual(ir.constraints[1].duration_ms, 10000)
        self.assertEqual(ir.constraints[2].duration_ms, 3600000)

    def test_ir_format_display(self):
        source = """
        system DisplaySys {
            state x = 1
            event Ev1
            on Ev1 { x = 2 }
            constraint Ev1 -> Ev1 within 100ms
        }
        """
        c_res = compile_source(source)
        formatted = format_ir(c_res.ir)
        self.assertIn("INTERMEDIATE REPRESENTATION (IR)", formatted)
        self.assertIn("DisplaySys", formatted)
        self.assertIn("STORE_STATE", formatted)
        self.assertIn("100 ms", formatted)


class TestIROptimizer(unittest.TestCase):
    """Unit tests for IR Optimization passes."""

    def test_dead_store_elimination(self):
        source = """
        system OptTest {
            state val = 0
            state status = "INIT"
            event Trigger
            on Trigger {
                val = 1
                val = 2
                val = 3
                status = "WORKING"
                status = "DONE"
            }
        }
        """
        c_res = compile_source(source)
        optimizer = IROptimizer()
        opt_ir, stats = optimizer.optimize(c_res.ir)

        # Before: LABEL, 3 stores to val, 2 stores to status, END = 7 instructions
        self.assertEqual(stats.initial_instructions, 7)
        # Redundant stores removed: val=1, val=2, status="WORKING" = 3
        self.assertEqual(stats.redundant_stores_removed, 3)
        # After: LABEL, val=3, status="DONE", END = 4 instructions
        self.assertEqual(stats.final_instructions, 4)
        self.assertEqual(stats.instructions_eliminated, 3)

        stores = [inst for inst in opt_ir.instructions if inst.opcode == IROpCode.STORE_STATE]
        self.assertEqual(len(stores), 2)
        self.assertEqual(stores[0].arg1, "val")
        self.assertEqual(stores[0].arg2, 3)
        self.assertEqual(stores[1].arg1, "status")
        self.assertEqual(stores[1].arg2, "DONE")

    def test_multi_handler_optimization(self):
        source = """
        system MultiOpt {
            state x = 0
            event A
            event B
            on A {
                x = 10
                x = 20
            }
            on B {
                x = 30
                x = 40
            }
        }
        """
        c_res = compile_source(source)
        opt_ir, stats = IROptimizer().optimize(c_res.ir)
        self.assertEqual(stats.redundant_stores_removed, 2)
        self.assertEqual(stats.instructions_eliminated, 2)
        self.assertIn("A", opt_ir.handler_offsets)
        self.assertIn("B", opt_ir.handler_offsets)

    def test_no_redundant_stores_unchanged(self):
        source = """
        system CleanSys {
            state a = 1
            state b = 2
            event Fire
            on Fire {
                a = 10
                b = 20
            }
        }
        """
        c_res = compile_source(source)
        optimizer = IROptimizer()
        opt_ir, stats = optimizer.optimize(c_res.ir)
        self.assertEqual(stats.instructions_eliminated, 0)
        self.assertEqual(len(opt_ir.instructions), len(c_res.ir.instructions))

    def test_format_optimization_comparison(self):
        source = """
        system CompareSys {
            state x = 0
            event Ev
            on Ev {
                x = 1
                x = 2
            }
        }
        """
        c_res = compile_source(source)
        opt_ir, stats = IROptimizer().optimize(c_res.ir)
        text = format_optimization_comparison(c_res.ir, opt_ir, stats)
        self.assertIn("IR OPTIMIZATION COMPARISON", text)
        self.assertIn("Instructions Eliminated", text)
        self.assertIn("Eliminated redundant store", text)


class TestBytecodeGenerator(unittest.TestCase):
    """Unit tests for Bytecode synthesis and formatting."""

    def test_bytecode_generation(self):
        source = """
        system BytecodeSys {
            state active = false
            event Alert
            on Alert {
                active = true
            }
        }
        """
        c_res = compile_source(source)
        bc_gen = BytecodeGenerator()
        compiled = bc_gen.generate(c_res.ir)

        self.assertEqual(compiled.system_name, "BytecodeSys")
        self.assertIn("Alert", compiled.handler_table)
        opcodes = [inst.opcode for inst in compiled.instructions]
        expected_opcodes = [
            OpCode.ENTER_HANDLER,
            OpCode.PUSH_CONST,
            OpCode.STORE_STATE,
            OpCode.EXIT_HANDLER,
            OpCode.HALT,
        ]
        self.assertEqual(opcodes, expected_opcodes)

    def test_bytecode_offsets_contiguous(self):
        source = """
        system ContigSys {
            state a = 1
            state b = "hi"
            event Ev
            on Ev {
                a = 2
                b = "bye"
            }
        }
        """
        c_res = compile_source(source)
        compiled = BytecodeGenerator().generate(c_res.ir)
        offsets = [inst.offset for inst in compiled.instructions]
        self.assertEqual(offsets, list(range(len(compiled.instructions))))

    def test_bytecode_format_display(self):
        source = """
        system BcDisplay {
            state num = 100
            event Tick
            on Tick { num = 200 }
        }
        """
        c_res = compile_source(source)
        compiled = BytecodeGenerator().generate(c_res.ir)
        text = format_bytecode(compiled)
        self.assertIn("SEQUENT BYTECODE", text)
        self.assertIn("ENTER_HANDLER", text)
        self.assertIn("PUSH_CONST", text)
        self.assertIn("STORE_STATE", text)
        self.assertIn("HALT", text)


class TestVirtualMachine(unittest.TestCase):
    """Unit tests for the SEQUENT Virtual Machine execution engine."""

    def test_vm_initialization_and_reset(self):
        source = """
        system VmInit {
            state mode = "STANDBY"
            state level = 5
            event Start
            on Start {
                mode = "ACTIVE"
                level = 10
            }
        }
        """
        c_res = compile_source(source)
        vm = VirtualMachine(c_res.bytecode)
        self.assertEqual(vm.states["mode"], "STANDBY")
        self.assertEqual(vm.states["level"], 5)

        changes = vm.execute_handler("Start")
        self.assertEqual(len(changes), 2)
        self.assertEqual(vm.states["mode"], "ACTIVE")
        self.assertEqual(vm.states["level"], 10)

        vm.reset()
        self.assertEqual(vm.states["mode"], "STANDBY")
        self.assertEqual(vm.states["level"], 5)

    def test_vm_unhandled_event(self):
        source = """
        system VmUnhandled {
            state x = 1
            event DeclaredOnly
        }
        """
        c_res = compile_source(source)
        vm = VirtualMachine(c_res.bytecode)
        changes = vm.execute_handler("DeclaredOnly")
        self.assertEqual(changes, [])
        self.assertEqual(vm.states["x"], 1)

    def test_vm_stack_underflow_pop(self):
        source = """
        system UnderflowSys {
            state x = 1
            event Ev
        }
        """
        c_res = compile_source(source)
        compiled = c_res.bytecode
        # Inject an erroneous POP with empty stack
        compiled.instructions.insert(
            0,
            BytecodeInstruction(offset=0, opcode=OpCode.POP, arg=None, source_line=1)
        )
        compiled.handler_table["Ev"] = 0
        vm = VirtualMachine(compiled)
        with self.assertRaises(VMError) as ctx:
            vm.execute_handler("Ev")
        self.assertIn("stack underflow", str(ctx.exception).lower())

    def test_vm_stack_underflow_store(self):
        source = """
        system StoreUnderflow {
            state x = 1
            event Ev
        }
        """
        c_res = compile_source(source)
        compiled = c_res.bytecode
        # Inject an erroneous STORE_STATE with empty stack
        compiled.instructions.insert(
            0,
            BytecodeInstruction(offset=0, opcode=OpCode.STORE_STATE, arg="x", source_line=1)
        )
        compiled.handler_table["Ev"] = 0
        vm = VirtualMachine(compiled)
        with self.assertRaises(VMError) as ctx:
            vm.execute_handler("Ev")
        self.assertIn("stack underflow", str(ctx.exception).lower())

    def test_vm_undefined_state_load(self):
        source = """
        system UndefinedState {
            state x = 1
            event Ev
        }
        """
        c_res = compile_source(source)
        compiled = c_res.bytecode
        compiled.instructions.insert(
            0,
            BytecodeInstruction(offset=0, opcode=OpCode.LOAD_STATE, arg="nonExistent", source_line=1)
        )
        compiled.handler_table["Ev"] = 0
        vm = VirtualMachine(compiled)
        with self.assertRaises(VMError) as ctx:
            vm.execute_handler("Ev")
        self.assertIn("undefined state", str(ctx.exception).lower())


class TestTemporalRuntimeMonitoring(unittest.TestCase):
    """Unit tests for runtime temporal constraint satisfaction and violation."""

    def test_constraint_satisfied(self):
        constraints = [{
            "source": "Alarm",
            "target": "Sprinkler",
            "duration_ms": 5000,
            "raw_duration": "5s",
        }]
        monitor = TemporalRuntimeMonitor(constraints)

        # Alarm occurs at 0ms
        checks1 = monitor.record_event("Alarm", 0)
        self.assertEqual(len(checks1), 0)

        # Sprinkler occurs at 3200ms (within 5000ms limit)
        checks2 = monitor.record_event("Sprinkler", 3200)
        self.assertEqual(len(checks2), 1)
        self.assertEqual(checks2[0].status, "SATISFIED")
        self.assertEqual(checks2[0].elapsed_ms, 3200)
        self.assertEqual(checks2[0].limit_ms, 5000)

        timeouts = monitor.finalize()
        self.assertEqual(len(timeouts), 0)

    def test_constraint_exact_boundary_satisfied(self):
        constraints = [{
            "source": "A",
            "target": "B",
            "duration_ms": 1000,
            "raw_duration": "1s",
        }]
        monitor = TemporalRuntimeMonitor(constraints)
        monitor.record_event("A", 100)
        checks = monitor.record_event("B", 1100)
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].status, "SATISFIED")
        self.assertEqual(checks[0].elapsed_ms, 1000)

    def test_constraint_violated(self):
        constraints = [{
            "source": "Alarm",
            "target": "Sprinkler",
            "duration_ms": 5000,
            "raw_duration": "5s",
        }]
        monitor = TemporalRuntimeMonitor(constraints)

        monitor.record_event("Alarm", 0)
        # Sprinkler occurs at 7200ms (> 5000ms limit)
        checks = monitor.record_event("Sprinkler", 7200)
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].status, "VIOLATED")
        self.assertEqual(checks[0].elapsed_ms, 7200)

    def test_constraint_timeout(self):
        constraints = [{
            "source": "Alarm",
            "target": "Sprinkler",
            "duration_ms": 5000,
            "raw_duration": "5s",
        }]
        monitor = TemporalRuntimeMonitor(constraints)

        # Only Alarm occurs, Sprinkler never occurs
        monitor.record_event("Alarm", 0)
        timeouts = monitor.finalize()
        self.assertEqual(len(timeouts), 1)
        self.assertEqual(timeouts[0].status, "TIMEOUT")
        self.assertEqual(timeouts[0].source_event, "Alarm")
        self.assertEqual(timeouts[0].target_event, "Sprinkler")


class TestSequentRuntimeAndLogging(unittest.TestCase):
    """Unit tests for SequentRuntime simulation, execution logging, and JSON output."""

    def test_simulation_execution_and_json(self):
        source = """
        system SimTest {
            state count = 0
            event Step
            on Step {
                count = 1
            }
        }
        """
        c_res, exec_res = execute_source(source, event_timeline=[("Step", 500)])
        self.assertTrue(c_res.success)
        self.assertIsNotNone(exec_res)
        self.assertEqual(exec_res.initial_state["count"], 0)
        self.assertEqual(exec_res.final_state["count"], 1)
        self.assertEqual(exec_res.total_events, 1)

        # JSON validation
        json_str = exec_res.to_json()
        data = json.loads(json_str)
        self.assertEqual(data["system"], "SimTest")
        self.assertEqual(data["summary"]["total_events"], 1)
        self.assertEqual(data["summary"]["total_state_changes"], 1)
        self.assertIn("initial_state", data)
        self.assertIn("final_state", data)
        self.assertIn("events_dispatched", data)

    def test_empty_timeline_execution(self):
        source = """
        system EmptyTimeline {
            state x = 10
        }
        """
        c_res, exec_res = execute_source(source, event_timeline=[])
        self.assertTrue(c_res.success)
        self.assertIsNotNone(exec_res)
        self.assertEqual(exec_res.total_events, 0)
        self.assertEqual(exec_res.final_state["x"], 10)

    def test_parse_timeline_string(self):
        timeline = parse_timeline_string("Ev1@0ms, Ev2@3.2s, Ev3@1m")
        self.assertEqual(len(timeline), 3)
        self.assertEqual(timeline[0], ("Ev1", 0))
        self.assertEqual(timeline[1], ("Ev2", 3200))
        self.assertEqual(timeline[2], ("Ev3", 60000))


class TestPhase2EndToEndExamples(unittest.TestCase):
    """Integration tests running all actual Phase 2 example files."""

    def test_execution_example_file(self):
        path = Path("examples/execution.seq")
        source = path.read_text(encoding="utf-8")
        c_res, exec_res = execute_source(source)
        self.assertTrue(c_res.success)
        self.assertIsNotNone(exec_res)
        self.assertEqual(exec_res.final_state["active"], False)
        self.assertEqual(exec_res.final_state["team"], "AVAILABLE")
        self.assertEqual(exec_res.constraints_satisfied, 1)
        self.assertEqual(exec_res.constraints_violated, 0)

    def test_temporal_satisfied_example_file(self):
        path = Path("examples/temporal_satisfied.seq")
        source = path.read_text(encoding="utf-8")
        c_res, exec_res = execute_source(source)
        self.assertTrue(c_res.success)
        self.assertIsNotNone(exec_res)
        self.assertEqual(exec_res.constraints_satisfied, 2)
        self.assertEqual(exec_res.constraints_violated, 0)
        self.assertTrue(exec_res.success)

    def test_temporal_violated_example_file(self):
        path = Path("examples/temporal_violated.seq")
        source = path.read_text(encoding="utf-8")
        c_res, exec_res = execute_source(source)
        self.assertTrue(c_res.success)
        self.assertIsNotNone(exec_res)
        self.assertEqual(exec_res.constraints_satisfied, 1)
        self.assertEqual(exec_res.constraints_violated, 1)
        self.assertFalse(exec_res.success)

    def test_optimization_demo_example_file(self):
        path = Path("examples/optimization_demo.seq")
        source = path.read_text(encoding="utf-8")
        c_res = compile_source(source, optimize=True)
        self.assertTrue(c_res.success)
        self.assertIsNotNone(c_res.optimization_stats)
        self.assertEqual(c_res.optimization_stats.redundant_stores_removed, 4)
        self.assertEqual(c_res.optimization_stats.instructions_eliminated, 4)


if __name__ == "__main__":
    unittest.main()
