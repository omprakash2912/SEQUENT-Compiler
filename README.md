# SEQUENT – A Temporal Event-Driven Domain-Specific Language and Compiler

**Compiler Design Laboratory Project**  
**Academic Year:** Fall Semester 2026–27  
**Student:** JEERU OMPRAKASH REDDY  
**Registration Number:** 24BKT0080  
**Institution:** School of Computer Science and Engineering, VIT Vellore  

---

## 1. Project Overview

**SEQUENT** is a custom domain-specific language (DSL) and optimizing compiler engineered for modeling, verifying, and executing **temporal, event-driven reactive systems**.

Real-world event-driven systems—such as emergency dispatch coordination, industrial process monitoring, robotics failsafes, and smart-grid power management—depend fundamentally on two properties:
1. **Deterministic event handling and state mutation:** State transitions must occur predictably in response to arriving events.
2. **Explicit temporal constraints:** Dependent events must occur within strict, quantifiable time windows relative to predecessor events.

In conventional general-purpose programming languages, timing constraints and event ordering are typically managed through ad-hoc timer libraries, callback chains, or application-level polling logic. This can obscure temporal requirements and separate deadline specifications from language semantics.

SEQUENT addresses this by making states, events, handlers, and temporal deadlines **first-class constructs** of the language. The SEQUENT compiler statically validates declarations, types, and temporal bounds during compilation, translates programs into an intermediate representation (IR), optimizes instructions, generates stack-based bytecode, serializes to verified `.seqc` binary containers, and monitors temporal deadlines deterministically using a discrete-event simulation virtual machine and interactive Web IDE dashboard.

---

## 2. Key Idea and Novelty

The central concept in SEQUENT is the elevation of **temporal deadlines to first-class grammar and AST constructs**:

```sequent
constraint SourceEvent -> TargetEvent within Duration
```

- **First-Class Temporal Grammar:** Rather than relying on auxiliary configuration files or runtime timer calls, temporal relationships between events are part of the core language syntax.
- **Static Temporal Analysis:** During compilation, the front-end verifies that all constrained events exist in the symbol table, normalizes multi-unit durations (`ms`, `s`, `m`, `h`) into integer milliseconds, and flags undefined dependencies before execution.
- **Runtime Temporal Monitoring:** During virtual-time execution, the runtime and discrete-event engine track timestamps, match source-target event pairs, and calculate exact elapsed virtual time against declared deadlines.
- **Academic Scope:** SEQUENT does not claim to invent temporal logic or replace real-time operating systems. It demonstrates how temporal constraints can be seamlessly integrated across all classic compiler phases: from lexical tokens and parse trees to custom linear Intermediate Representation (IR), optimization, bytecode emission, and virtual-time verification.

---

## 3. Current Compiler Architecture Pipeline

The SEQUENT compiler implements an end-to-end pipeline spanning front-end analysis, middle-end optimization, and back-end execution:

```text
                     +---------------------------+
                     | SEQUENT Source Code (.seq) |
                     +---------------------------+
                                   |
                                   v
                         [ Lexical Analyzer ]
                         compiler/lexer.py
                                   |
                             Token Stream
                                   v
                   [ LL(1) Recursive-Descent Parser ]
                         compiler/parser.py
                                   |
                         Abstract Syntax Tree (AST)
                                   v
                        [ Semantic Analyzer ]
                     compiler/semantic_analyzer.py
                                   |
                              Symbol Table
                                   v
                    [ Static Temporal Analyzer ]
                     compiler/temporal_analyzer.py
                                   |
                     Normalized Constraint Specifications
                                   v
                       [ Linear IR Generator ]
                          compiler/ir.py
                                   |
                         Intermediate Representation
                                   v
                        [ IR Pass Optimizer ]
                     compiler/ir_optimizer.py
                                   |
                        Optimized Linear IR
                                   v
                      [ Bytecode Generator ]
                       compiler/bytecode.py
                                   |
                       +-----------+-----------+
                       |                       |
                       v                       v
            [ Bytecode Serializer ]      [ SEQUENT VM ]
            compiler/serializer.py       compiler/vm.py
                       |                       |
                       v                       v
               Binary Container       [ Discrete-Event Sim ]
                   (.seqc)           compiler/simulator.py
                       |                       |
                       +-----------+-----------+
                                   |
                                   v
                  [ Runtime Temporal Verification ]
                                   |
                                   v
                 +-----------------+-----------------+
                 |                                   |
                 v                                   v
       [ Structured Telemetry ]            [ Web IDE Dashboard ]
              (JSON)                        dashboard_server.py
```

---

## 4. Phase 1 — Front-End Compilation & Static Analysis

Phase 1 establishes the language specification, lexical analysis, syntactic parsing, AST construction, symbol resolution, and static temporal analysis.

### Language Specification & Grammar (EBNF)

```ebnf
Program         ::= "system" Identifier "{" SystemBody "}"
SystemBody      ::= { Declaration | Handler | Constraint }
Declaration     ::= StateDeclaration | EventDeclaration
StateDeclaration::= "state" Identifier "=" Literal
EventDeclaration::= "event" Identifier
Handler         ::= "on" Identifier "{" { Assignment } "}"
Assignment      ::= Identifier "=" Literal
Constraint      ::= "constraint" Identifier "->" Identifier "within" Duration
Literal         ::= Integer | Float | String | Boolean
Duration        ::= Integer TimeUnit
TimeUnit        ::= "ms" | "s" | "m" | "h"
```

### Front-End Modules

- **Tokens (`compiler/tokens.py`):** Defines `TokenType` enumeration covering keywords (`system`, `state`, `event`, `on`, `constraint`, `within`, `true`, `false`), literals (integer, float, string, boolean), operators (`=`, `->`), block delimiters (`{`, `}`), and time units.
- **Lexical Analyzer (`compiler/lexer.py`):** Scans raw source characters, strips comments (`//`) and whitespace, tracks 1-based line and column numbers, handles multi-character operators, and raises structured `LexerError` diagnostics on invalid characters or unterminated literals.
- **LL(1) Parser & AST (`compiler/parser.py`, `compiler/ast.py`):** Hand-written recursive-descent parser enforcing SEQUENT grammar with single-token lookahead. Builds a strongly typed AST hierarchy (`ProgramNode`, `StateDeclNode`, `EventDeclNode`, `HandlerNode`, `AssignmentNode`, `ConstraintNode`) with formatted tree visualization.
- **Symbol Table (`compiler/symbol_table.py`):** Manages scoped symbol entries for states and events, recording declaration names, inferred data types, initial values, and line coordinates.
- **Semantic Analyzer (`compiler/semantic_analyzer.py`):** Validates declaration uniqueness, detects redeclarations, verifies that event handlers reference declared events, enforces state variable type safety on assignment, and flags undeclared identifiers.
- **Static Temporal Analyzer (`compiler/temporal_analyzer.py`):** Validates that constraint source and target events are declared in the symbol table, rejects non-positive or zero durations, and normalizes all time units into base integer milliseconds:
  - $1\text{ ms} = 1\text{ ms}$
  - $1\text{ s} = 1{,}000\text{ ms}$
  - $1\text{ m} = 60{,}000\text{ ms}$
  - $1\text{ h} = 3{,}600{,}000\text{ ms}$

---

## 5. Phase 2 — Intermediate Representation, Optimization, Bytecode & VM

Phase 2 introduces the compiler middle-end and execution engine, translating verified ASTs into an intermediate representation, optimizing instructions, generating bytecode, and running programs on a stack-based virtual machine.

### Intermediate Representation (`compiler/ir.py`)

A custom linear Intermediate Representation (IR) decoupling front-end AST representations from back-end machine execution:

| IR Opcode | Operands | Description |
| :--- | :--- | :--- |
| `DECLARE_STATE` | `name, initial_value` | Allocates and initializes state variable |
| `DECLARE_EVENT` | `name` | Registers event identifier |
| `DECLARE_CONSTRAINT` | `src_event, tgt_event, ms` | Declares static temporal constraint in normalized milliseconds |
| `LABEL_HANDLER` | `event_name` | Marks entry point for event handler block |
| `STORE_STATE` | `state_name, value` | Assigns evaluated literal value to state variable |
| `EMIT_EVENT` | `event_name, timestamp_ms` | Emits simulated event at specified timestamp |
| `CHECK_CONSTRAINT` | `src_event, tgt_event, ms` | Encodes runtime temporal check instruction |
| `END_HANDLER` | `event_name` | Marks exit point for event handler block |
| `NOP` | `None` | No-operation instruction |

### IR Optimization Passes (`compiler/ir_optimizer.py`)

The IR optimizer inspects handler blocks to eliminate redundant instructions:
1. **Dead Store Elimination (DSE):** When multiple assignments to the same state variable occur within a single handler without intervening reads, preceding assignments are eliminated.
2. **Redundant Assignment Elimination:** Assignments setting a variable to its current known compile-time value are pruned.
3. **Optimization Statistics:** Tracks instruction counts before and after optimization, calculating percentage reduction and displaying comparative side-by-side diffs.

### Bytecode Instruction Set (`compiler/bytecode.py`)

The optimizer outputs linear bytecode instructions executed by the stack machine:

| Bytecode Opcode | Argument | Stack Effect | Description |
| :--- | :--- | :--- | :--- |
| `PUSH_CONST` | `literal` | `[] -> [val]` | Push literal constant onto operand stack |
| `POP` | `None` | `[val] -> []` | Discard top value on operand stack |
| `STORE_STATE` | `state_name` | `[val] -> []` | Pop value and store into named state variable |
| `LOAD_STATE` | `state_name` | `[] -> [val]` | Load value of named state variable onto operand stack |
| `ENTER_HANDLER` | `event_name` | `[] -> []` | Enter event handler scope |
| `EXIT_HANDLER` | `event_name` | `[] -> []` | Exit event handler scope |
| `EMIT_EVENT` | `(event_name, ms)` | `[] -> []` | Dispatch an event at simulated virtual clock time |
| `CHECK_TEMPORAL` | `(src, tgt, ms)` | `[] -> []` | Perform runtime temporal constraint check |
| `HALT` | `None` | `[] -> []` | Halt virtual machine execution |

### Stack-Based SEQUENT Virtual Machine (`compiler/vm.py`)

The SEQUENT Virtual Machine (SVM) executes generated bytecode using:
- **Evaluation Stack:** LIFO stack for arithmetic and assignment evaluation.
- **State Store:** Key-value environment holding current program state variables.
- **Event Dispatch Table:** Map from event names to instruction offset entry points.
- **Safe Error Recovery:** Traps stack underflow, undefined state loads, and unhandled event dispatches cleanly.

### Runtime Temporal Monitoring (`compiler/runtime.py`)

The runtime environment maintains an event arrival log and evaluates active constraints on each incoming event. It records state mutation traces and outputs structured execution reports.

---

## 6. Phase 3 — Discrete-Event Simulator, Binary Serialization & Telemetry

Phase 3 extends the execution engine with deterministic virtual-time simulation, binary bytecode container serialization, and comprehensive structured telemetry.

### Deterministic Virtual-Time Simulation (`compiler/simulator.py`)

> [!IMPORTANT]
> SEQUENT's execution engine operates via **deterministic virtual-time discrete-event simulation**, not non-deterministic real-time physical clock execution. Time advances instantaneously between scheduled event points.

- **Priority Queue Engine:** Implemented using Python's `heapq` module as a min-heap priority queue.
- **Virtual Integer Clock:** Time is tracked strictly as non-negative integer milliseconds ($t \ge 0$).
- **Deterministic 3-Level Tie-Breaking:** When multiple events are scheduled, ordering is resolved deterministically without race conditions:
  $$\text{Tuple: } (\text{timestamp\_ms}, \text{ priority}, \text{ sequence\_id}, \text{ event\_name})$$
  1. *Timestamp:* Events with lower timestamps execute first.
  2. *Priority:* Lower numeric integer indicates higher priority (default: `10`).
  3. *FIFO Sequence Counter:* Tie-breaker preserving chronological insertion order.
- **State Transitions History:** Every mutation records `(timestamp_ms, triggering_event, variable, old_value, new_value)`.

### Binary Container Serialization (`compiler/serializer.py` — `.seqc`)

SEQUENT implements a 16-byte fixed binary container format for compiled bytecode:

```text
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|       'S'     |      'E'      |      'Q'      |      'C'      | (Magic: 0x53455143)
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|          Version (2B)         |           Flags (2B)          | (v1, Big-Endian)
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                      Payload Length (4B)                      | (Big-Endian uint32)
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                      CRC32 Checksum (4B)                      | (IEEE 802.3 uint32)
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                        Payload Data...                        |
|   (Serialized JSON bytecode, symbols, handlers, constraints)  |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

- **Validation:** When loading a `.seqc` file, the loader verifies:
  1. 4-byte magic signature matches `b"SEQC"`.
  2. Format version equals `1`.
  3. Total byte size matches `16 + payload_len`.
  4. IEEE 802.3 CRC32 computed over payload matches the header checksum.
- **Direct Execution:** Loading a valid `.seqc` file **bypasses source compilation entirely** and executes the verified bytecode directly on the virtual machine.

### Structured JSON Telemetry

The simulator outputs execution traces containing:
- System name, simulation duration, and termination timestamp.
- Initial and final state variables.
- Total events processed and total state mutations.
- Array of state transition records.
- Detailed temporal constraint verification results.

### Performance Benchmarking (`compiler/benchmark.py`)

Provides built-in micro-benchmarking measuring:
- Front-end compilation throughput across 50 iterations.
- Virtual-time discrete-event simulation throughput across 1,000 and 5,000 event workloads.

---

## 7. Temporal Verification Semantics

SEQUENT's runtime verification engine validates temporal constraints during simulation according to four formal verdicts:

$$\text{Constraint: } S \to T \text{ within } D$$

Let $t_S$ be the arrival time of source event $S$, $t_T$ be the arrival time of target event $T$, and $\Delta t = t_T - t_S$ be the elapsed virtual time.

| Verification Verdict | Condition | Description |
| :--- | :--- | :--- |
| **`SATISFIED`** | $\Delta t \le D$ | Target event arrived strictly within the allotted deadline. |
| **`SATISFIED` (Exact Boundary)** | $\Delta t = D$ | Target event arrived exactly on the deadline boundary ($\Delta t = D$). Verified as valid. |
| **`VIOLATED`** | $\Delta t > D$ | Target event arrived, but elapsed virtual time exceeded deadline $D$. |
| **`TIMEOUT`** | $t_S \text{ occurred, } t_T \text{ never occurred}$ | Source event arrived, but simulation terminated without target event arrival ($\Delta t = \infty$). |

---

## 8. Web IDE & Compiler Dashboard

SEQUENT includes an interactive browser-based Web IDE and dashboard operated by a lightweight local Python server (`dashboard_server.py`):

- **Local Address:** `http://127.0.0.1:8000`
- **Zero Third-Party Dependencies:** Pure HTML5, CSS3, and ES6 JavaScript. No external libraries, node packages, or CDN scripts.
- **Synchronized 16-Stage Visual Inspector:**
  1. *Source Editor:* Editable SEQUENT source code with line numbers and error highlighting.
  2. *Lexer (Tokens):* Interactive token stream grid.
  3. *Parser / AST:* Hierarchical syntax tree visualizer.
  4. *Symbol Table:* Registered states, events, and inferred types.
  5. *Semantic Analysis:* Type checks and identifier resolution summary.
  6. *Temporal Analysis:* Static deadline normalization table.
  7. *Intermediate Representation (IR):* Custom linear Intermediate Representation (IR) view.
  8. *IR Optimization:* Comparative optimization view with metrics.
  9. *Bytecode Disassembly:* Virtual machine opcode disassembly.
  10. *Virtual Machine (VM):* Stack machine state and dispatch table.
  11. *Event Simulation:* Priority queue execution log and schedule.
  12. *Temporal Verification:* Formal constraint verification audit.
  13. *Visual Timeline & Gantt View:* Interactive SVG Gantt chart with Unicode legend:
      - `Event Arrival`
      - `Satisfied (Δt ≤ D)`
      - `Violated (Δt > D)`
      - `Timeout (Δt = ∞)`
  14. *State Transitions:* Filterable mutation log (`old -> new`).
  15. *Telemetry JSON:* Formatted and raw execution trace telemetry.
  16. *.seqc Binary Inspector:* 16-byte container header fields and CRC32 verification.

---

## 9. Developer Diagnostics & Error Experience

The Web IDE features an IDE-grade compiler diagnostics engine (`compiler/diagnostics.py`):

- **Multi-Layer Editor Highlighting:**
  - Red background line tint and accent bar on lines with syntax or semantic errors.
  - Squiggly red underline under the exact token range.
  - Red `❌` marker in the editor line gutter.
- **Dockable Problems Panel:**
  - Lists compilation and verification errors with stage badge (`LEXER`, `PARSER`, `SEMANTIC`, `TEMPORAL`, `VERIFICATION`), exact 1-based line/column coordinates, and error descriptions.
  - Includes **"Go to Line"** navigation setting editor cursor and selection range directly to the erroneous token.
- **Fuzzy "Did You Mean?" Suggestions:**
  - When an undeclared event or state is referenced, the diagnostic engine calculates string similarity against declared symbols and suggests the closest valid identifier.
- **One-Click Safe Fixes:**
  - Proposes non-destructive fixes (e.g., auto-appending missing closing braces or replacing mistyped symbol names).

---

## 10. SEQUENT Assistant (Rule-Based)

> [!NOTE]
> The SEQUENT Assistant is a **deterministic, rule-based offline tool** running inside `compiler/diagnostics.py`. It is **NOT an LLM or cloud AI**.

The Assistant provides:
- **What went wrong?** A clear, human-readable explanation of why the compiler rejected the input.
- **Declared in System:** Visual badge chips displaying all valid state variables and events currently declared in scope.
- **How to fix it:** Concrete syntax and declaration guidance.
- **One-Click Actions:** `[Go to Line]` and `[Apply Fix]` buttons.
- **Clean State:** Displays an all-green verification report with compiler stage badges when the program compiles cleanly.

---

## 11. Built-in Boilerplate Templates

The Web IDE includes 5 pre-configured, syntactically valid boilerplate templates for testing and demonstration:

1. **Emergency Response System (`emergency_response`):** Dispatch coordinator with 5s and 30m response deadlines.
2. **Industrial Monitoring System (`industrial_monitoring`):** Pressure threshold safety loop with automated relief valve and stabilization monitoring.
3. **Smart Building Grid (`smart_building`):** Power grid failure detector with auxiliary generator startup and 1-hour grid restoration deadline.
4. **Simple Timer System (`simple_timer`):** Discrete periodic timer loop with tick verification and expiration handler.
5. **Fault Detection & Failsafe (`fault_detection`):** Critical sensor fault detector with automated failsafe engagement within 500ms.

---

## 12. Project Directory Structure

```text
D:\SEQUENT
├── compiler/
│   ├── __init__.py               # Package exports and unified helper functions
│   ├── ast.py                    # AST node hierarchy and tree pretty-printer
│   ├── benchmark.py              # Performance benchmark harness
│   ├── bytecode.py               # Bytecode instruction set and emitter
│   ├── diagnostics.py            # Diagnostic data models, assistant, and templates
│   ├── ir.py                     # Custom linear Intermediate Representation (IR)
│   ├── ir_optimizer.py           # Dead store elimination and IR optimization passes
│   ├── lexer.py                  # Lexical analyzer with line/column tracking
│   ├── parser.py                 # Hand-written LL(1) recursive-descent parser
│   ├── runtime.py                # Runtime event execution and temporal monitor
│   ├── semantic_analyzer.py      # Semantic validation and type checking
│   ├── serializer.py             # Binary .seqc container encoding and CRC32 verification
│   ├── simulator.py              # Priority-queue discrete-event virtual simulator
│   ├── symbol_table.py           # Symbol table management and scope lookup
│   ├── temporal_analyzer.py      # Static temporal validation and duration normalization
│   ├── tokens.py                 # Token definitions and TokenType enumeration
│   └── vm.py                     # Stack-based SEQUENT Virtual Machine
├── dashboard/
│   ├── app.js                    # Web IDE client application logic (zero dependencies)
│   ├── favicon.ico               # Multi-size binary favicon (16x16, 32x32, 48x48, 64x64)
│   ├── favicon.svg               # SVG brand vector icon
│   ├── index.html                # Single-page Web IDE layout and stage views
│   └── style.css                 # Dark theme IDE styles and responsive grid layout
├── examples/
│   ├── actual_run.json           # Telemetry output from sample run
│   ├── EmergencyResponseViolated.seqc # Pre-compiled binary demonstrating temporal violation
│   ├── execution.seq             # Runtime execution sample
│   ├── optimization_demo.seq     # IR optimization sample
│   ├── phase3_complex.seq        # Multi-stage complex workflow sample
│   ├── phase3_events.json        # External JSON event schedule
│   ├── phase3_simulation.json    # Simulation telemetry export
│   ├── phase3_simulation.seq     # Building management simulation source
│   ├── phase3_simulation.seqc    # Compiled binary of building management simulation
│   ├── phase3_timeout.json       # Timeout simulation telemetry export
│   ├── phase3_timeout.seq        # Sample demonstrating constraint timeout
│   ├── semantic_error.seq        # Intentionally invalid: undefined identifier
│   ├── syntax_error.seq          # Intentionally invalid: missing closing brace
│   ├── temporal_error.seq        # Intentionally invalid: undeclared event constraint
│   ├── temporal_satisfied.seq    # Verified temporal satisfaction sample
│   ├── temporal_violated.seq     # Verified temporal violation sample
│   ├── type_error.seq            # Intentionally invalid: type mismatch assignment
│   └── valid.seq                 # Primary reference emergency response system
├── tests/
│   ├── __init__.py               # Test package indicator
│   ├── test_ide_server.py        # Web IDE, diagnostics, and HTTP API integration tests
│   ├── test_phase1.py            # Phase 1 front-end unit and integration tests
│   ├── test_phase2.py            # Phase 2 IR, optimizer, bytecode, and VM tests
│   └── test_phase3.py            # Phase 3 simulator, .seqc serialization, and telemetry tests
├── docs/                         # Academic documentation, reports, and build scripts
├── presentation/                 # Presentation slides and review materials
├── screenshots/                  # Project screenshots and visual assets
├── dashboard_server.py           # Local HTTP server for Web IDE (standard library)
├── main.py                       # Main command-line compiler and execution driver
├── README.md                     # Comprehensive project documentation
└── requirements.txt              # Standard project requirements file
```

---

## 13. How to Run

All commands can be executed in PowerShell from the project root (`D:\SEQUENT`):

### 1. Basic Source Compilation

```powershell
python main.py examples\valid.seq
```

### 2. Inspect Compiler Front-End Stages

```powershell
# Token stream
python main.py examples\valid.seq --tokens

# Abstract Syntax Tree (AST)
python main.py examples\valid.seq --ast

# Symbol table
python main.py examples\valid.seq --symbols

# Static temporal constraints
python main.py examples\valid.seq --temporal
```

### 3. Inspect IR, Optimization & Bytecode

```powershell
# Linear Intermediate Representation
python main.py examples\valid.seq --ir

# IR Optimization comparison (before vs after)
python main.py examples\valid.seq --optimize

# Virtual Machine bytecode disassembly
python main.py examples\valid.seq --bytecode
```

### 4. Execute Simulation with Custom Event Timeline

```powershell
# Default simulation
python main.py examples\valid.seq --simulate

# Custom timeline string with timestamped events
python main.py examples\valid.seq --simulate --events "EmergencyDetected@0ms, TeamDispatched@3200ms, IncidentResolved@5000ms"

# Output structured telemetry as JSON
python main.py examples\valid.seq --simulate --json
```

### 5. Binary Bytecode Serialization (`.seqc`)

```powershell
# Compile source and emit .seqc binary container
python main.py examples\valid.seq --emit-seqc

# Inspect disassembly directly from .seqc binary
python main.py examples\valid.seqc --bytecode

# Execute simulation directly from .seqc binary (bypasses source compilation)
python main.py examples\valid.seqc --simulate --events "EmergencyDetected@0ms, TeamDispatched@3200ms, IncidentResolved@5000ms"
```

### 6. Run Performance Benchmark

```powershell
python main.py examples\valid.seq --benchmark
```

### 7. Launch the Web IDE & Dashboard

```powershell
python dashboard_server.py
```

Open a web browser and navigate to:
```text
http://127.0.0.1:8000
```

### 8. Run the Automated Test Suite

```powershell
python -m unittest discover -v
```

---

## 14. Testing & Verification Results

The SEQUENT compiler is validated by an automated, deterministic test suite:

```powershell
python -m unittest discover -v
```

```text
----------------------------------------------------------------------
Ran 120 tests in 0.510s

OK
```

### Test Suite Breakdown

| Test Module | Test Focus | Tests | Status |
| :--- | :--- | :---: | :---: |
| `tests/test_phase1.py` | Lexer tokens, line/col tracking, LL(1) parser, AST structure, symbol table, semantic analysis, static temporal analysis, and error cases | 29 | **29/29 PASS** |
| `tests/test_phase2.py` | IR generation, DSE optimization, bytecode generation, stack VM execution, runtime event logging, and temporal monitoring | 26 | **26/26 PASS** |
| `tests/test_phase3.py` | Discrete-event simulator, priority queue tie-breaking, `.seqc` serialization, header/CRC32 integrity, and telemetry | 24 | **24/24 PASS** |
| `tests/test_ide_server.py` | Web IDE endpoints (`/api/compile`, `/api/compile-run`, `/api/emit-seqc`, `/api/load-seqc`), diagnostics, assistant, templates, and static assets | 41 | **41/41 PASS** |
| **Total** | **Comprehensive end-to-end compiler verification** | **120** | **120/120 PASS** |

---

## 15. Example Programs Catalog

The repository includes ready-to-run examples in the `examples/` directory:

| File | Type | Description |
| :--- | :--- | :--- |
| `valid.seq` | Source | Reference emergency response workflow with 5s and 30m constraints. |
| `temporal_satisfied.seq` | Source | Multi-event sequence satisfying all temporal deadlines. |
| `temporal_violated.seq` | Source | Sequence configured to trigger a temporal deadline violation ($\Delta t > D$). |
| `phase3_simulation.seq` | Source | Smart building power grid management with failover verification. |
| `phase3_timeout.seq` | Source | Workflow demonstrating a constraint timeout ($\Delta t = \infty$). |
| `phase3_complex.seq` | Source | Comprehensive system with multiple state mutations, events, and constraints. |
| `optimization_demo.seq` | Source | Contains redundant stores to demonstrate Dead Store Elimination. |
| `syntax_error.seq` | Source | Intentionally invalid syntax (missing closing brace) for diagnostics testing. |
| `semantic_error.seq` | Source | Intentionally invalid semantic reference (assignment to undeclared state). |
| `temporal_error.seq` | Source | Intentionally invalid temporal constraint (references undeclared target event). |
| `type_error.seq` | Source | Intentionally invalid type assignment (string literal assigned to boolean state). |
| `EmergencyResponseViolated.seqc` | Binary | Compiled binary container demonstrating direct VM execution and violation verdict. |
| `phase3_simulation.seqc` | Binary | Compiled binary container of building management system. |
| `phase3_events.json` | JSON | External event schedule demonstrating JSON timeline resolution. |

---

## 16. Technologies & Dependencies

- **Language:** Python 3.10+
- **Standard Library Components Utilized:**
  - `heapq` — Min-heap priority queue implementation for the discrete-event simulator.
  - `struct` — Big-Endian binary header packing and unpacking for `.seqc` files.
  - `zlib` — IEEE 802.3 CRC32 checksum computation for container integrity.
  - `http.server` — Zero-dependency HTTP server hosting the Web IDE API and dashboard.
  - `unittest` — Unit and integration test execution.
  - `argparse`, `json`, `dataclasses`, `difflib`, `pathlib` — CLI parsing, data formatting, and symbol matching.
- **Frontend Stack (Web IDE):**
  - Pure HTML5, CSS3, and ES6 JavaScript (Zero npm packages, zero external CDNs, fully offline).

---

## 17. Technical Limitations & Realistic Future Work

To maintain academic honesty, the following boundaries of the current implementation are noted:

1. **Virtual Time vs. Physical Time:** SEQUENT uses discrete-event virtual time simulation. It does not interface with physical hardware clocks or real-time operating system (RTOS) interrupt timers.
2. **Literal Expressions:** State assignments currently accept literal constants (integers, floats, booleans, strings). General arithmetic expressions ($a + b * c$) and conditional branches (`if`/`else`) inside handlers are natural future additions.
3. **Single System Scope:** Each compilation unit defines a single `system` block. Multi-system communication across networks is not currently modeled.
4. **Bytecode Format:** The `.seqc` binary format encapsulates an IEEE 802.3 CRC32-verified container with serialized bytecode. It is designed for the SEQUENT Virtual Machine (SVM) and is not native machine code (such as x86-64 or ARM).

---

## 18. Academic Project Information

- **Student Name:** JEERU OMPRAKASH REDDY
- **Registration Number:** 24BKT0080
- **Course:** Compiler Design Laboratory
- **Degree:** B.Tech. Computer Science and Engineering (Spec. in Blockchain Technology)
- **Institution:** School of Computer Science and Engineering, Vellore Institute of Technology (VIT), Vellore
- **Semester:** Fall Semester 2026–27
