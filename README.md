# SEQUENT

### A Temporal Event-Driven Domain-Specific Language and Compiler

**Compiler Design Laboratory Project**

**Student:** JEERU OMPRAKASH REDDY  
**Registration Number:** 24BKT0080  
**Milestone:** Phase 1 – Problem Definition, System Design, and Initial Prototype  
**Review:** Review 1 – Project Proposal, System Design, and Initial Front-End Prototype

---

## 1. Project Overview

**SEQUENT** is a domain-specific language (DSL) and compiler designed for modeling and statically analyzing **temporal, event-driven reactive systems**.

Many event-driven systems—such as emergency dispatch, industrial automation, robotics, and monitoring systems—depend on correct event ordering and time-bounded responses.

Conventional programming approaches often express event timing and ordering through application logic or external mechanisms, which can make temporal requirements harder to express and validate consistently.

SEQUENT introduces events, state transitions, and temporal constraints as language-level constructs, allowing the compiler to perform static validation of declarations, references, types, and temporal requirements.

---

## 2. Phase 1 Scope & Status

> [!NOTE]
> This repository currently contains the **Phase 1 Initial Prototype** developed for **Review 1**.

The Phase 1 implementation focuses strictly on the **compiler front-end**:

- Lexical analysis with line and column tracking
- Hand-written recursive-descent parsing
- Abstract Syntax Tree (AST) construction and tree visualization
- Symbol table creation and scope resolution
- Semantic validation
- Type checking
- Declaration uniqueness validation
- Reference checking
- Static temporal constraint validation
- Duration normalization

### Intentionally Deferred Components — Phase 2 & Phase 3 Roadmap

In accordance with the planned project milestones, the following components are **not yet implemented** in Phase 1:

- Intermediate Representation (IR) generation
- Control-flow and temporal IR optimizers
- Bytecode generator and instruction encoder
- SEQUENT Virtual Machine (SVM) runtime
- Runtime event simulation and queue management
- Runtime temporal deadline monitoring
- JSON execution trace logging
- Web dashboard and interactive visualization

---

## 3. Compiler Architecture Pipeline

The Phase 1 compiler pipeline is organized as follows:

```text
SEQUENT SOURCE CODE (.seq)
           │
           ▼
    [ Lexical Analyzer ]
       compiler/lexer.py
           │
      Token Stream
      compiler/tokens.py
           │
           ▼
 [ Recursive-Descent Parser ]
       compiler/parser.py
           │
   Abstract Syntax Tree
       compiler/ast.py
           │
           ▼
   [ Semantic Analyzer ]
 compiler/semantic_analyzer.py
           │
      Symbol Table
 compiler/symbol_table.py
           │
           ▼
[ Temporal Constraint Analyzer ]
 compiler/temporal_analyzer.py
           │
           ▼
 COMPILATION REPORT / CLI
       INSPECTION
```

---

## 4. SEQUENT Language V1 Specification

### Keywords

```text
system
state
event
on
constraint
within
true
false
```

### Literals and Types

- **Boolean:** `true`, `false`
- **Integer:** `0`, `5`, `42`
- **Float:** `3.14`, `12.5`
- **String:** `"AVAILABLE"`, `"DISPATCHED"`

### Operators & Delimiters

- `=` : State assignment and initialization
- `->` : Temporal sequence transition
- `{`, `}` : Block delimiters
- `//` : Single-line comments

### Time Units & Normalization

- `ms` : Milliseconds
- `s` : Seconds
- `m` : Minutes
- `h` : Hours

Normalization is performed as follows:

```text
1 ms = 1 ms
1 s  = 1,000 ms
1 m  = 60,000 ms
1 h  = 3,600,000 ms
```

### Formal Grammar — EBNF

```ebnf
Program
    ::= "system" Identifier "{" SystemBody "}"

SystemBody
    ::= { Declaration | Handler | Constraint }

Declaration
    ::= StateDeclaration
      | EventDeclaration

StateDeclaration
    ::= "state" Identifier "=" Literal

EventDeclaration
    ::= "event" Identifier

Handler
    ::= "on" Identifier "{" { Assignment } "}"

Assignment
    ::= Identifier "=" Literal

Constraint
    ::= "constraint" Identifier "->" Identifier "within" Duration

Literal
    ::= Integer
      | Float
      | String
      | Boolean

Duration
    ::= Integer TimeUnit

TimeUnit
    ::= "ms" | "s" | "m" | "h"
```

---

## 5. Sample SEQUENT Program

The primary demonstration program is available in:

```text
examples/valid.seq
```

```sequent
system EmergencyResponse {

    state active = false

    state team = "AVAILABLE"

    event EmergencyDetected

    event TeamDispatched

    event IncidentResolved

    on EmergencyDetected {

        active = true

        team = "DISPATCHED"

    }

    on IncidentResolved {

        active = false

        team = "AVAILABLE"

    }

    constraint EmergencyDetected -> TeamDispatched within 5s

    constraint TeamDispatched -> IncidentResolved within 30m

}
```

This example represents a simple emergency-response workflow:

```text
EmergencyDetected
        │
        ▼
TeamDispatched
        │
        ▼
IncidentResolved
```

with temporal requirements:

```text
EmergencyDetected
        │
        └──→ TeamDispatched within 5 seconds

TeamDispatched
        │
        └──→ IncidentResolved within 30 minutes
```

---

## 6. Project Directory Structure

```text
D:\SEQUENT

│
├── compiler/
│   ├── __init__.py
│   ├── tokens.py
│   ├── lexer.py
│   ├── ast.py
│   ├── parser.py
│   ├── symbol_table.py
│   ├── semantic_analyzer.py
│   └── temporal_analyzer.py
│
├── examples/
│   ├── valid.seq
│   ├── syntax_error.seq
│   ├── semantic_error.seq
│   ├── temporal_error.seq
│   └── type_error.seq
│
├── tests/
│   ├── __init__.py
│   └── test_phase1.py
│
├── docs/
│
├── presentation/
│
├── screenshots/
│
├── main.py
├── README.md
├── requirements.txt
└── .gitignore
```

### Core Compiler Modules

| File                   | Purpose                                                   |
| ---------------------- | --------------------------------------------------------- |
| `tokens.py`            | Token definitions and `TokenType` enumeration             |
| `lexer.py`             | Lexical analysis and tokenization                         |
| `ast.py`               | AST node hierarchy and tree representation                |
| `parser.py`            | Hand-written recursive-descent parser                     |
| `symbol_table.py`      | Symbol table and symbol management                        |
| `semantic_analyzer.py` | Semantic validation and type checking                     |
| `temporal_analyzer.py` | Temporal constraint validation and duration normalization |
| `main.py`              | Compiler CLI driver                                       |

---

## 7. How to Run the Compiler

The compiler driver is executed using `main.py`.

### Basic Compilation

From the project root:

```powershell
python main.py examples\valid.seq
```

### Expected Output

```text
LEXICAL ANALYSIS ✓
SYNTAX ANALYSIS ✓
AST CONSTRUCTION ✓
SYMBOL TABLE ✓
SEMANTIC ANALYSIS ✓
TEMPORAL ANALYSIS ✓
COMPILATION SUCCESSFUL
```

---

### Compiler Inspection Flags

The compiler provides inspection modes for examining different stages of the compilation process.

#### 1. Inspect Token Stream

```powershell
python main.py examples\valid.seq --tokens
```

#### 2. Inspect Abstract Syntax Tree

```powershell
python main.py examples\valid.seq --ast
```

#### 3. Inspect Symbol Table

```powershell
python main.py examples\valid.seq --symbols
```

#### 4. Inspect Normalized Temporal Constraints

```powershell
python main.py examples\valid.seq --temporal
```

These inspection modes allow the intermediate results of the compiler front-end to be examined during development and demonstration.

---

### Error Handling Demonstrations

The repository contains dedicated examples for different compiler error categories.

#### 1. Syntax Error

```powershell
python main.py examples\syntax_error.seq
```

Demonstrates a syntax error such as a missing closing brace.

#### 2. Semantic Error

```powershell
python main.py examples\semantic_error.seq
```

Demonstrates an undefined state identifier.

#### 3. Temporal Error

```powershell
python main.py examples\temporal_error.seq
```

Demonstrates a temporal constraint referencing an undefined event.

#### 4. Type Error

```powershell
python main.py examples\type_error.seq
```

Demonstrates a type mismatch such as assigning a string literal to a Boolean state.

---

## 8. How to Run Tests

The test suite uses Python's built-in `unittest` framework.

### Run the Complete Test Suite

```powershell
python -m unittest discover -s tests -v
```

### Run the Test File Directly

```powershell
python -m unittest tests\test_phase1.py
```

---

### Current Test Result

The current Phase 1 implementation has:

```text
Ran 29 tests in 0.027s

OK
```

**29/29 tests passed successfully.**

The test suite contains deterministic unit and integration tests covering:

- Lexer tokenization
- Keywords
- Identifiers
- Literals
- Comments and whitespace
- Duration tokens
- Operators and symbols
- Line and column tracking
- Lexer error handling
- Recursive-descent parser
- Grammar enforcement
- Syntax error reporting
- AST construction
- AST pretty printing
- Symbol table operations
- Duplicate declarations
- Undefined states
- Undefined events
- Type mismatch detection
- Temporal constraint validation
- Non-positive duration rejection
- Duration unit normalization
- End-to-end compilation of example programs

---

## 9. Current Phase 1 Limitations

### Static Analysis Only

Temporal constraints are currently validated statically against declared events and their durations.

Runtime event simulation and runtime deadline monitoring are planned for later phases.

### Literal Expressions

State assignments currently support direct literals.

Arithmetic expressions, conditional expressions, and guards are planned for later milestones.

### Single System Scope

Each `.seq` file currently specifies a single `system` declaration block.

Additional language features can be introduced in future phases as the compiler evolves.

---

## 10. Development Status

### Phase 1 — Completed

| Component                | Status           |
| ------------------------ | ---------------- |
| Token Definitions        | ✅ Implemented   |
| Lexical Analyzer         | ✅ Implemented   |
| Line & Column Tracking   | ✅ Implemented   |
| Recursive-Descent Parser | ✅ Implemented   |
| AST Construction         | ✅ Implemented   |
| Symbol Table             | ✅ Implemented   |
| Semantic Analysis        | ✅ Implemented   |
| Type Checking            | ✅ Implemented   |
| Reference Validation     | ✅ Implemented   |
| Temporal Analysis        | ✅ Implemented   |
| Duration Normalization   | ✅ Implemented   |
| Error Diagnostics        | ✅ Implemented   |
| CLI Compiler Driver      | ✅ Implemented   |
| Automated Tests          | ✅ 29/29 Passing |

### Future Phases

| Component                   | Status     |
| --------------------------- | ---------- |
| Intermediate Representation | 🔲 Planned |
| IR Optimization             | 🔲 Planned |
| Bytecode Generation         | 🔲 Planned |
| SEQUENT Virtual Machine     | 🔲 Planned |
| Event Simulation            | 🔲 Planned |
| Runtime Temporal Monitoring | 🔲 Planned |
| JSON Execution Trace        | 🔲 Planned |
| Web Dashboard               | 🔲 Planned |

---

## 11. Planned Complete Compiler Architecture

The long-term SEQUENT architecture is planned as:

```text
SEQUENT SOURCE CODE
        │
        ▼
      Lexer
        │
        ▼
     Parser
        │
        ▼
       AST
        │
        ▼
Symbol Table + Semantic Analysis
        │
        ▼
 Temporal Analysis
        │
        ▼
       IR
        │
        ▼
   Optimization
        │
        ▼
     Bytecode
        │
        ▼
   SEQUENT VM
        │
        ▼
 Event Simulation
        │
        ▼
 JSON Execution Log
        │
        ▼
   Web Dashboard
```

The Phase 1 implementation currently covers the compiler front-end up to temporal analysis.

---

## 12. Compiler Design Concepts Demonstrated

SEQUENT demonstrates the following compiler design concepts:

- Lexical analysis
- Tokenization
- Syntax analysis
- Recursive-descent parsing
- Abstract Syntax Trees
- Symbol tables
- Semantic analysis
- Type checking
- Declaration and reference validation
- Static validation
- Domain-Specific Language design
- Temporal constraint analysis
- Duration normalization
- Compiler error diagnostics
- Unit and integration testing

---

## 13. Technologies Used

- **Python** — Compiler implementation
- **Python `unittest`** — Automated testing
- **Recursive-Descent Parsing** — Syntax analysis
- **Custom DSL Design** — SEQUENT language
- **Git** — Version control
- **GitHub** — Source code hosting and project collaboration

The current Phase 1 implementation uses Python's standard library for the compiler and testing components.

---

## 14. Repository Contents

The repository contains the currently implemented Phase 1 compiler source code, example SEQUENT programs, automated tests, and supporting project documentation.

### Main Implementation

```text
compiler/
main.py
```

### Example Programs

```text
examples/
```

### Automated Tests

```text
tests/
```

### Documentation

```text
docs/
```

---

## 15. Academic Project

**Project:** SEQUENT – A Temporal Event-Driven Domain-Specific Language and Compiler

**Course:** Compiler Design Laboratory

**Milestone:** Phase 1 – Problem Definition, System Design, and Initial Prototype

**Review:** Review 1 – Project Proposal, System Design, and Initial Front-End Prototype

**Student:** JEERU OMPRAKASH REDDY

**Registration Number:** 24BKT0080

**Institution:** VIT Vellore

**Program:** B.Tech Computer Science and Engineering

**Specialization:** Blockchain Technology

---

## 16. Project Status

```text
SEQUENT Phase 1
────────────────────────────────

Compiler Front-End       COMPLETE ✓
Lexical Analysis         COMPLETE ✓
Syntax Analysis          COMPLETE ✓
AST Construction         COMPLETE ✓
Symbol Table             COMPLETE ✓
Semantic Analysis        COMPLETE ✓
Temporal Analysis        COMPLETE ✓
Automated Testing        29/29 ✓

────────────────────────────────

IR                       PLANNED
Optimization             PLANNED
Bytecode                 PLANNED
SEQUENT VM               PLANNED
Event Simulation         PLANNED
Web Dashboard            PLANNED
```

---

## Authors

**JEERU OMPRAKASH REDDY**

**Registration Number:** 24BKT0080

---

### Academic Project — Compiler Design Laboratory

SEQUENT is developed as an academic project for compiler design learning, experimentation, and demonstration.
