"""
SEQUENT Compiler - Web IDE Server & Event Timeline Test Suite
Tests:
- JSON event file input vs timeline string input
- Web IDE compilation pipeline API (/api/compile)
- Web IDE simulation & compile-run API (/api/compile-run)
- Compiler error diagnostics (lexer, parser, semantic, temporal)
- Source code mutation produces real changed execution results
- Binary bytecode (.seqc) emission and loading roundtrip
- Real HTTP server request/response integration
"""

import base64
import json
from pathlib import Path
import threading
import time
import unittest
import urllib.request

from unittest.mock import patch

from compiler import compile_source, resolve_events_timeline, parse_timeline_string
from compiler.serializer import BytecodeSerializer
from dashboard_server import (
    compile_for_ide,
    simulate_for_ide,
    execute_seqc_for_ide,
    format_seqc_error,
    get_examples_catalog,
    create_app_server,
)
from compiler.diagnostics import (
    CompilerDiagnostic,
    create_diagnostic_from_error,
    calculate_column_span,
    TEMPLATES,
)


class TestEventTimelineResolution(unittest.TestCase):
    """Tests resolving event timelines from files, JSON strings, and timeline strings."""

    def test_json_event_file_loading(self):
        json_path = "examples/phase3_events.json"
        self.assertTrue(Path(json_path).is_file(), f"File {json_path} should exist")
        events = resolve_events_timeline(json_path)
        self.assertEqual(len(events), 4)
        self.assertEqual(events[0][0], "PeakTrafficDetected")
        self.assertEqual(events[0][1], 0)
        self.assertEqual(events[0][2], 5)
        self.assertEqual(events[1][0], "PriorityLaneOpened")
        self.assertEqual(events[1][1], 2500)
        self.assertEqual(events[3][0], "NormalFlowRestored")
        self.assertEqual(events[3][1], 8000)
        self.assertEqual(events[3][2], 10)

    def test_timeline_string_parsing(self):
        spec = "SensorAlert@0ms, AuxiliaryPowerOnline@1500ms, SystemStabilized@4s"
        events = resolve_events_timeline(spec)
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0], ("SensorAlert", 0))
        self.assertEqual(events[1], ("AuxiliaryPowerOnline", 1500))
        self.assertEqual(events[2], ("SystemStabilized", 4000))

    def test_raw_json_string_parsing(self):
        raw_json = '[{"event": "AlarmA", "timestamp_ms": 100, "priority": 2}, {"event": "AlarmB", "timestamp_ms": 300}]'
        events = resolve_events_timeline(raw_json)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0], ("AlarmA", 100, 2))
        self.assertEqual(events[1], ("AlarmB", 300, 10))

    def test_empty_spec(self):
        self.assertEqual(resolve_events_timeline(""), [])
        self.assertEqual(resolve_events_timeline("   "), [])


class TestWebIDECompilerAPI(unittest.TestCase):
    """Unit tests for compile_for_ide and simulate_for_ide functions."""

    def setUp(self):
        self.valid_source = Path("examples/valid.seq").read_text(encoding="utf-8")
        self.syntax_error_source = Path("examples/syntax_error.seq").read_text(encoding="utf-8")
        self.semantic_error_source = Path("examples/semantic_error.seq").read_text(encoding="utf-8")
        self.temporal_error_source = Path("examples/temporal_error.seq").read_text(encoding="utf-8")

    def test_compile_for_ide_success(self):
        res = compile_for_ide(self.valid_source)
        self.assertTrue(res["success"])
        self.assertEqual(res["system_name"], "EmergencyResponse")
        self.assertEqual(res["stages_status"]["lexer"], "ok")
        self.assertEqual(res["stages_status"]["parser"], "ok")
        self.assertEqual(res["stages_status"]["symbols"], "ok")
        self.assertEqual(res["stages_status"]["semantic"], "ok")
        self.assertEqual(res["stages_status"]["temporal"], "ok")
        self.assertEqual(res["stages_status"]["ir"], "ok")
        self.assertEqual(res["stages_status"]["optimization"], "ok")
        self.assertEqual(res["stages_status"]["bytecode"], "ok")

        # Verify tokens
        self.assertGreater(len(res["tokens"]), 10)
        self.assertIn("type", res["tokens"][0])
        self.assertIn("value", res["tokens"][0])

        # Verify AST
        self.assertIn("formatted", res["ast"])
        self.assertIn("tree", res["ast"])

        # Verify symbols
        self.assertEqual(len(res["symbols"]["states"]), 2)
        self.assertEqual(len(res["symbols"]["events"]), 3)

        # Verify temporal
        self.assertEqual(len(res["temporal"]["constraints"]), 2)
        self.assertEqual(res["temporal"]["constraints"][0]["duration_ms"], 5000)

        # Verify bytecode
        self.assertGreater(res["bytecode"]["total_instructions"], 0)

    def test_compile_syntax_error_diagnostic(self):
        res = compile_for_ide(self.syntax_error_source)
        self.assertFalse(res["success"])
        self.assertEqual(res["error"]["stage"], "PARSER")
        self.assertEqual(res["stages_status"]["parser"], "failed")
        self.assertIsNotNone(res["error"]["line"])
        self.assertIsNotNone(res["error"]["message"])

    def test_compile_semantic_error_diagnostic(self):
        res = compile_for_ide(self.semantic_error_source)
        self.assertFalse(res["success"])
        self.assertEqual(res["error"]["stage"], "SEMANTIC")
        self.assertEqual(res["stages_status"]["semantic"], "failed")
        self.assertIn("Undefined", res["error"]["message"])

    def test_compile_temporal_error_diagnostic(self):
        res = compile_for_ide(self.temporal_error_source)
        self.assertFalse(res["success"])
        self.assertEqual(res["error"]["stage"], "TEMPORAL")
        self.assertEqual(res["stages_status"]["temporal"], "failed")
        self.assertIn("Undefined event 'UnknownEvent'", res["error"]["message"])

        # Verify semantic analysis flagged unresolved identifier
        self.assertEqual(res["stages_status"]["semantic"], "warning")
        self.assertEqual(res["partial_stages"]["semantic"]["status"], "UNRESOLVED_IDENTIFIERS")
        self.assertIn("UnknownEvent", res["partial_stages"]["semantic"]["message"])

        # Verify AST has duration string (no 'undefined')
        ast_constraints = res["partial_stages"]["ast"]["tree"]["constraints"]
        self.assertEqual(len(ast_constraints), 1)
        self.assertEqual(ast_constraints[0]["duration"], "5s")
        self.assertEqual(ast_constraints[0]["target_event"], "UnknownEvent")

        # Verify temporal partial stage contains current source constraint and failure status
        temporal_constraints = res["partial_stages"]["temporal"]["constraints"]
        self.assertEqual(len(temporal_constraints), 1)
        self.assertEqual(temporal_constraints[0]["source"], "EmergencyDetected")
        self.assertEqual(temporal_constraints[0]["target"], "UnknownEvent")
        self.assertEqual(temporal_constraints[0]["raw_duration"], "5s")
        self.assertEqual(temporal_constraints[0]["status"], "UNDEFINED: 'UnknownEvent'")

    def test_ast_duration_values_on_valid_source(self):
        res = compile_for_ide(self.valid_source)
        self.assertTrue(res["success"])
        ast_constraints = res["ast"]["tree"]["constraints"]
        self.assertEqual(len(ast_constraints), 2)
        self.assertEqual(ast_constraints[0]["duration"], "5s")
        self.assertEqual(ast_constraints[1]["duration"], "30m")

    def test_no_stale_data_across_compilations(self):
        # First compile valid source
        res_valid = compile_for_ide(self.valid_source)
        self.assertTrue(res_valid["success"])
        self.assertEqual(len(res_valid["temporal"]["constraints"]), 2)

        # Then compile temporal error source
        res_err = compile_for_ide(self.temporal_error_source)
        self.assertFalse(res_err["success"])
        # Ensure error output has exactly the 1 constraint from temporal_error.seq, NOT valid.seq
        err_constraints = res_err["partial_stages"]["temporal"]["constraints"]
        self.assertEqual(len(err_constraints), 1)
        self.assertEqual(err_constraints[0]["target"], "UnknownEvent")
        self.assertNotIn("TeamDispatched", [c["target"] for c in err_constraints])

    def test_simulation_for_ide(self):
        res = simulate_for_ide(self.valid_source, events_spec="EmergencyDetected@0ms, TeamDispatched@3200ms, IncidentResolved@5000ms")
        self.assertTrue(res["success"])
        self.assertEqual(res["system_name"], "EmergencyResponse")
        self.assertEqual(res["summary"]["total_events"], 3)
        self.assertEqual(res["summary"]["constraints_satisfied"], 2)
        self.assertEqual(res["summary"]["constraints_violated"], 0)
        self.assertIn("telemetry_json", res)
        # Parse telemetry
        telemetry = json.loads(res["telemetry_json"])
        self.assertEqual(telemetry["system"], "EmergencyResponse")

    def test_source_mutation_changes_compiler_output(self):
        """Verifies that changing source code in the IDE produces different actual results."""
        source1 = """
        system TestToggle {
            state active = false
            event Flip
            on Flip {
                active = true
            }
        }
        """
        source2 = """
        system TestToggle {
            state active = true
            event Flip
            on Flip {
                active = false
            }
        }
        """
        res1 = simulate_for_ide(source1, events_spec="Flip@0ms")
        res2 = simulate_for_ide(source2, events_spec="Flip@0ms")

        # Initial state was false in source1, true in source2
        self.assertEqual(res1["initial_state"]["active"], False)
        self.assertEqual(res2["initial_state"]["active"], True)

        # Final state was true in source1, false in source2
        self.assertEqual(res1["final_state"]["active"], True)
        self.assertEqual(res2["final_state"]["active"], False)

    def test_examples_catalog(self):
        catalog = get_examples_catalog()
        self.assertGreaterEqual(len(catalog), 6)
        for ex in catalog:
            self.assertIn("id", ex)
            self.assertIn("name", ex)
            self.assertIn("source", ex)
            self.assertIn("default_events", ex)
            self.assertTrue(len(ex["source"]) > 0, f"Source for example {ex['id']} should not be empty")


class TestHTTPServerIntegration(unittest.TestCase):
    """Runs a local test server instance and verifies HTTP API endpoints."""

    @classmethod
    def setUpClass(cls):
        # Bind to port 0 for an automatically allocated free ephemeral port
        cls.server = create_app_server("127.0.0.1", 0)
        cls.host, cls.port = cls.server.server_address
        cls.base_url = f"http://{cls.host}:{cls.port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _post_json(self, endpoint: str, data: dict) -> dict:
        req = urllib.request.Request(
            f"{self.base_url}{endpoint}",
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            self.assertEqual(response.status, 200)
            return json.loads(response.read().decode("utf-8"))

    def _get_json(self, endpoint: str) -> Any:
        with urllib.request.urlopen(f"{self.base_url}{endpoint}", timeout=5) as response:
            self.assertEqual(response.status, 200)
            return json.loads(response.read().decode("utf-8"))

    def test_http_health(self):
        data = self._get_json("/api/health")
        self.assertEqual(data["status"], "ok")

    def test_http_get_examples(self):
        examples = self._get_json("/api/examples")
        self.assertIsInstance(examples, list)
        self.assertGreaterEqual(len(examples), 5)

    def test_http_get_templates(self):
        templates = self._get_json("/api/templates")
        self.assertIsInstance(templates, list)
        self.assertEqual(len(templates), 5)
        names = [t["name"] for t in templates]
        self.assertIn("Emergency Response", names)
        self.assertIn("Industrial Monitoring", names)
        self.assertIn("Smart Building", names)
        self.assertIn("Simple Timer", names)
        self.assertIn("Fault Detection", names)

    def test_http_compile_endpoint(self):
        source = Path("examples/valid.seq").read_text(encoding="utf-8")
        data = self._post_json("/api/compile", {"source": source})
        self.assertTrue(data["success"])
        self.assertEqual(data["system_name"], "EmergencyResponse")
        self.assertIn("tokens", data)
        self.assertIn("ast", data)
        self.assertIn("bytecode", data)

    def test_http_compile_run_endpoint(self):
        source = Path("examples/valid.seq").read_text(encoding="utf-8")
        data = self._post_json(
            "/api/compile-run",
            {"source": source, "events": "EmergencyDetected@0ms, TeamDispatched@3200ms, IncidentResolved@5000ms"},
        )
        self.assertTrue(data["success"])
        self.assertEqual(data["summary"]["constraints_satisfied"], 2)
        self.assertIn("compiler", data)
        self.assertEqual(data["compiler"]["stages_status"]["bytecode"], "ok")

    def test_http_emit_and_load_seqc_roundtrip(self):
        source = Path("examples/phase3_simulation.seq").read_text(encoding="utf-8")
        # 1. Emit .seqc
        emit_resp = self._post_json("/api/emit-seqc", {"source": source})
        self.assertTrue(emit_resp["success"])
        self.assertEqual(emit_resp["magic"], "SEQC")
        self.assertEqual(emit_resp["version"], 1)
        self.assertTrue(emit_resp["crc32_hex"].startswith("0x"))
        b64_data = emit_resp["base64_data"]

        # 2. Load .seqc
        load_resp = self._post_json(
            "/api/load-seqc",
            {"base64_data": b64_data, "events": "SensorAlert@0ms, AuxiliaryPowerOnline@1500ms, SystemStabilized@4000ms"},
        )
        self.assertTrue(load_resp["success"])
        self.assertEqual(load_resp["system_name"], "BuildingManagement")
        self.assertEqual(load_resp["summary"]["constraints_satisfied"], 2)
        self.assertEqual(load_resp["seqc_metadata"]["magic"], "SEQC")

    def test_http_static_assets(self):
        # 1. Root index.html
        with urllib.request.urlopen(f"{self.base_url}/", timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/html", resp.headers.get("Content-Type"))
            html = resp.read().decode("utf-8")
            self.assertIn("SEQUENT | Web IDE & Compiler Dashboard", html)
            self.assertIn("sourceEditor", html)

        # 2. style.css
        with urllib.request.urlopen(f"{self.base_url}/style.css", timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/css", resp.headers.get("Content-Type"))
            css = resp.read().decode("utf-8")
            self.assertIn("ide-header", css)

        # 3. app.js
        with urllib.request.urlopen(f"{self.base_url}/app.js", timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("javascript", resp.headers.get("Content-Type"))
            js = resp.read().decode("utf-8")
            self.assertIn("DOMContentLoaded", js)

        # 4. favicon.ico
        with urllib.request.urlopen(f"{self.base_url}/favicon.ico", timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("image/x-icon", resp.headers.get("Content-Type"))
            self.assertGreater(len(resp.read()), 0)

        # 5. favicon.svg
        with urllib.request.urlopen(f"{self.base_url}/favicon.svg", timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("image/svg+xml", resp.headers.get("Content-Type"))
            self.assertGreater(len(resp.read()), 0)

    def test_http_error_response(self):
        # Syntax error compilation
        bad_source = "system Broken { state x = 10"  # missing closing brace
        resp = self._post_json("/api/compile", {"source": bad_source})
        self.assertFalse(resp["success"])
        self.assertEqual(resp["error"]["stage"], "PARSER")
        self.assertIsNotNone(resp["error"]["message"])


    def test_http_run_seqc_endpoint(self):
        source = Path("examples/valid.seq").read_text(encoding="utf-8")
        emit_resp = self._post_json("/api/emit-seqc", {"source": source})
        self.assertTrue(emit_resp["success"])
        b64_data = emit_resp["base64_data"]

        # POST /api/run-seqc
        run_resp = self._post_json(
            "/api/run-seqc",
            {"base64_data": b64_data, "events": "EmergencyDetected@0ms, TeamDispatched@1000ms, IncidentResolved@2000ms"},
        )
        self.assertTrue(run_resp["success"])
        self.assertTrue(run_resp["is_seqc"])
        self.assertEqual(run_resp["summary"]["constraints_satisfied"], 2)
        self.assertEqual(run_resp["stages_status"]["lexer"], "skipped")

    def test_http_load_seqc_error_handling(self):
        bad_b64 = base64.b64encode(b"NOT_A_VALID_SEQC_CONTAINER").decode("ascii")
        data = self._post_json("/api/load-seqc", {"base64_data": bad_b64})
        self.assertFalse(data["success"])
        self.assertEqual(data["error"]["stage"], "SEQC")
        self.assertIn("SEQC LOAD ERROR", data["error"]["message"])


class TestSeqcBinaryExecution(unittest.TestCase):
    """Tests for standalone .seqc binary loading, deserialization, and direct VM execution."""

    def setUp(self):
        self.source = Path("examples/valid.seq").read_text(encoding="utf-8")
        self.compiled = compile_source(self.source, optimize=True).bytecode
        self.valid_seqc_bytes = BytecodeSerializer.serialize(self.compiled)

    def test_execute_seqc_for_ide_success(self):
        res = execute_seqc_for_ide(self.valid_seqc_bytes, "EmergencyDetected@0ms, TeamDispatched@1000ms, IncidentResolved@2000ms")
        self.assertTrue(res["success"])
        self.assertTrue(res["is_seqc"])
        self.assertEqual(res["system_name"], "EmergencyResponse")

        # Verify 8 metadata fields
        meta = res["seqc_metadata"]
        self.assertEqual(meta["magic"], "SEQC")
        self.assertEqual(meta["version"], 1)
        self.assertIn("flags", meta)
        self.assertIn("payload_len", meta)
        self.assertTrue(meta["crc32_hex"].startswith("0x"))
        self.assertGreater(meta["total_instructions"], 0)
        self.assertEqual(meta["system_name"], "EmergencyResponse")
        self.assertEqual(meta["handler_count"], 2)

        # Verify stages status shows skipped for source compilation stages
        stages = res["stages_status"]
        for st in ["lexer", "parser", "symbols", "semantic", "temporal", "ir", "optimization"]:
            self.assertEqual(stages[st], "skipped", f"Stage {st} should be skipped for .seqc")
        self.assertEqual(stages["bytecode"], "ok")
        self.assertEqual(stages["vm"], "ok")
        self.assertEqual(stages["simulation"], "ok")
        self.assertEqual(stages["verification"], "ok")

    def test_lexer_is_never_invoked_for_seqc(self):
        with patch("compiler.lexer.Lexer.__init__", side_effect=AssertionError("Lexer should never be called")):
            res = execute_seqc_for_ide(self.valid_seqc_bytes, "EmergencyDetected@0ms, TeamDispatched@1000ms")
            self.assertTrue(res["is_seqc"])

    def test_source_vs_seqc_execution_equivalence(self):
        timeline = "EmergencyDetected@0ms, TeamDispatched@2000ms, IncidentResolved@3000ms"
        src_res = simulate_for_ide(self.source, events_spec=timeline)
        seqc_res = execute_seqc_for_ide(self.valid_seqc_bytes, events_spec=timeline)

        self.assertEqual(src_res["final_state"], seqc_res["final_state"])
        self.assertEqual(src_res["summary"]["total_events"], seqc_res["summary"]["total_events"])
        self.assertEqual(src_res["summary"]["total_state_changes"], seqc_res["summary"]["total_state_changes"])
        self.assertEqual(src_res["summary"]["constraints_satisfied"], seqc_res["summary"]["constraints_satisfied"])
        self.assertEqual(src_res["summary"]["constraints_violated"], seqc_res["summary"]["constraints_violated"])
        self.assertEqual(src_res["simulation"]["duration_ms"], seqc_res["simulation"]["duration_ms"])

    def test_emergency_response_violated_seqc(self):
        violated_file = Path("EmergencyResponseViolated.seqc")
        self.assertTrue(violated_file.is_file(), "EmergencyResponseViolated.seqc must exist")
        raw_bytes = violated_file.read_bytes()
        timeline = "EmergencyDetected@0ms, TeamDispatched@6000ms, IncidentResolved@7000ms"
        res = execute_seqc_for_ide(raw_bytes, events_spec=timeline, filename="EmergencyResponseViolated.seqc")

        self.assertFalse(res["success"])
        self.assertEqual(res["summary"]["constraints_satisfied"], 1)
        self.assertEqual(res["summary"]["constraints_violated"], 1)
        self.assertEqual(res["stages_status"]["verification"], "failed")
        self.assertEqual(res["stages_status"]["lexer"], "skipped")

    def test_invalid_magic_header_error(self):
        bad_magic = b"NOPE" + self.valid_seqc_bytes[4:]
        res = execute_seqc_for_ide(bad_magic)
        self.assertFalse(res["success"])
        self.assertIn("SEQC LOAD ERROR: Invalid SEQC magic header", res["error"]["message"])

    def test_unsupported_version_error(self):
        import struct
        bad_ver = self.valid_seqc_bytes[:4] + struct.pack(">H", 99) + self.valid_seqc_bytes[6:]
        res = execute_seqc_for_ide(bad_ver)
        self.assertFalse(res["success"])
        self.assertIn("SEQC LOAD ERROR: Unsupported SEQC version", res["error"]["message"])

    def test_checksum_mismatch_error(self):
        corrupted = bytearray(self.valid_seqc_bytes)
        corrupted[-1] ^= 0xFF
        res = execute_seqc_for_ide(bytes(corrupted))
        self.assertFalse(res["success"])
        self.assertIn("SEQC LOAD ERROR: CRC32 checksum mismatch", res["error"]["message"])

    def test_truncated_payload_error(self):
        truncated = self.valid_seqc_bytes[:10]
        res = execute_seqc_for_ide(truncated)
        self.assertFalse(res["success"])
        self.assertIn("SEQC LOAD ERROR: Truncated SEQC payload", res["error"]["message"])

    def test_format_seqc_error_helper(self):
        self.assertEqual(format_seqc_error("Magic mismatch: got b'1234'"), "SEQC LOAD ERROR: Invalid SEQC magic header. (Magic mismatch: got b'1234')")
        self.assertEqual(format_seqc_error("Unsupported version 5"), "SEQC LOAD ERROR: Unsupported SEQC version. (Unsupported version 5)")
        self.assertIn("SEQC LOAD ERROR: CRC32 checksum mismatch", format_seqc_error("CRC32 checksum mismatch: expected 0x1234, computed 0x5678"))
        self.assertIn("SEQC LOAD ERROR: Truncated SEQC payload", format_seqc_error("Truncated header: expected 16 bytes, got 8"))
        self.assertEqual(format_seqc_error("Something weird"), "SEQC LOAD ERROR: Something weird")


class TestIDEDiagnosticsAndAssistant(unittest.TestCase):
    """Tests VS Code-style diagnostics, rule-based assistant, fuzzy suggestion, and templates."""

    def test_compiler_diagnostic_data_model(self):
        diag = CompilerDiagnostic(
            stage="TEMPORAL",
            severity="ERROR",
            line=6,
            column=5,
            end_column=15,
            message="Temporal constraint references undeclared event 'UnknownEvent'",
            explanation="The constraint references an undefined event.",
            suggestion="Did you mean event 'TeamDispatched'?",
            token="UnknownEvent",
            token_column=37,
            token_end_column=49,
            code_fix={"type": "replace_token", "target": "UnknownEvent", "replacement": "TeamDispatched", "line": 6},
            declared_events=["EmergencyDetected", "TeamDispatched"],
            declared_states=["active"],
        )
        d = diag.to_dict()
        self.assertEqual(d["stage"], "TEMPORAL")
        self.assertEqual(d["severity"], "ERROR")
        self.assertEqual(d["line"], 6)
        self.assertEqual(d["column"], 5)
        self.assertEqual(d["token"], "UnknownEvent")
        self.assertEqual(d["token_column"], 37)
        self.assertEqual(d["token_end_column"], 49)
        self.assertIn("TeamDispatched", d["code_fix"]["replacement"])

    def test_calculate_column_span(self):
        source = "system Test {\n    constraint A -> UnknownEvent within 5s\n}"
        col, end_col, tok_col, tok_end_col = calculate_column_span(source, line=2, column=5, token="UnknownEvent")
        self.assertEqual(col, 5)
        self.assertEqual(end_col, 15)
        self.assertEqual(tok_col, 21)
        self.assertEqual(tok_end_col, 33)

    def test_lexer_error_diagnostics(self):
        source = "system InvalidChar { state x = @ }"
        res = compile_for_ide(source)
        self.assertFalse(res["success"])
        self.assertIn("diagnostics", res)
        self.assertGreater(len(res["diagnostics"]), 0)
        d = res["diagnostics"][0]
        self.assertEqual(d["stage"], "LEXER")
        self.assertEqual(d["severity"], "ERROR")
        self.assertEqual(d["line"], 1)
        self.assertIn("@", d["message"])
        self.assertIn("not a valid token", d["explanation"])

    def test_parser_error_diagnostics_with_fix(self):
        source = "system MissingBrace {\n    state x = 1\n"
        res = compile_for_ide(source)
        self.assertFalse(res["success"])
        self.assertIn("diagnostics", res)
        d = res["diagnostics"][0]
        self.assertEqual(d["stage"], "PARSER")
        self.assertIn("code_fix", d)
        self.assertEqual(d["code_fix"]["type"], "append_text")

    def test_semantic_error_diagnostics(self):
        source = Path("examples/semantic_error.seq").read_text(encoding="utf-8")
        res = compile_for_ide(source)
        self.assertFalse(res["success"])
        self.assertIn("diagnostics", res)
        d = res["diagnostics"][0]
        self.assertEqual(d["stage"], "SEMANTIC")
        self.assertIn("suggestion", d)

    def test_temporal_error_fuzzy_suggestion_and_coordinates(self):
        source = Path("examples/temporal_error.seq").read_text(encoding="utf-8")
        res = compile_for_ide(source)
        self.assertFalse(res["success"])
        self.assertIn("diagnostics", res)
        self.assertGreater(len(res["diagnostics"]), 0)
        d = res["diagnostics"][0]
        self.assertEqual(d["stage"], "TEMPORAL")
        self.assertEqual(d["line"], 6)
        self.assertEqual(d["column"], 5)
        self.assertEqual(d["token"], "UnknownEvent")
        self.assertIsNotNone(d.get("code_fix"))
        self.assertIn("EmergencyDetected", d.get("declared_events", []))
        self.assertIn("EmergencyDetected", d.get("code_fix", {}).get("replacement", ""))

    def test_clean_compilation_diagnostics_empty(self):
        source = Path("examples/valid.seq").read_text(encoding="utf-8")
        res = compile_for_ide(source)
        self.assertTrue(res["success"])
        self.assertIn("diagnostics", res)
        self.assertEqual(len(res["diagnostics"]), 0)

    def test_runtime_verification_diagnostics(self):
        source = Path("examples/temporal_violated.seq").read_text(encoding="utf-8")
        res = simulate_for_ide(source, events_spec="EmergencyDetected@0ms, TeamDispatched@7200ms, IncidentResolved@8500ms")
        self.assertFalse(res["success"])
        self.assertIn("diagnostics", res)
        self.assertGreater(len(res["diagnostics"]), 0)
        d = res["diagnostics"][0]
        self.assertEqual(d["stage"], "VERIFICATION")
        self.assertIn("VIOLATED", d["message"])

    def test_templates_validity_all_compile(self):
        self.assertEqual(len(TEMPLATES), 5)
        for key, tmpl in TEMPLATES.items():
            self.assertIn("name", tmpl)
            self.assertIn("code", tmpl)
            self.assertIn("default_events", tmpl)
            res = compile_for_ide(tmpl["code"])
            self.assertTrue(res["success"], f"Template '{key}' failed to compile: {res.get('error')}")
            self.assertEqual(res["diagnostics"], [])


if __name__ == "__main__":
    unittest.main()
