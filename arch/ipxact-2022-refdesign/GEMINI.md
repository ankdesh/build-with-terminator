# GEMINI.md — IP-XACT 2022 Lean Profile Tooling: Project Constitution

This file is the authoritative guide for any AI agent (Gemini or otherwise) working on this
project. Read this file fully before making any changes or generating any artifacts.

---

## 1. Project Purpose

This project provides tooling for modeling the **internal microarchitecture of IP blocks**
(CPUs, NPUs, accelerators) using a **lean subset of the IEEE 1685-2022 (IP-XACT 2022)**
standard. The lean profile strips away SoC-level bus constructs and focuses exclusively on
**direct, point-to-point communication** between IP units (no buses, no bus interfaces).

The three active tools are:

| Tool | Location | Description |
|---|---|---|
| **Converter** | `src/tools/converter/` | Migrates IP-XACT 2014 XML → 2022 with flagging |
| **Validator** | `src/tools/validator/` | Validates any IP-XACT XML against the official 2022 XSD |
| **Generator Skill** | `skills/ipxact-generator/` | Gemini Skill: generates Cat-1-only 2022 XML from natural language |

---

## 2. Organizational Constants

| Constant | Value |
|---|---|
| **Vendor name** | `saiti` |
| **IP-XACT 2022 Namespace URI** | `http://www.accellera.org/XMLSchema/IPXACT/1685-2022` |
| **IP-XACT 2014 Namespace URI** | `http://www.accellera.org/XMLSchema/IPXACT/1685-2014` |
| **Accellera VE Namespace** | `http://www.accellera.org/XMLSchema/IPXACT/1685-2022-VE` |
| **Accellera Cond VE Namespace** | `http://www.accellera.org/XMLSchema/IPXACT/1685-2022-VE-COND-1.0` |
| **XSD Cache Location** | `src/tools/validator/schemas/` |

---

## 3. IP-XACT 2022 Element Categories (The Lean Profile)

### Category 1 — MANDATORY (Phase 1 scope — use ONLY these)

These are the only elements permitted in generated IP-XACT documents. The Generator Skill
MUST NOT emit any element from Category 2 or Category 3.

| Element (local name) | XML Tag | Purpose |
|---|---|---|
| `component` | `ipxact:component` | Defines one functional IP block (e.g., IF stage, ID stage) |
| `design` | `ipxact:design` | Wires component instances together via ad-hoc connections |
| `designConfiguration` | `ipxact:designConfiguration` | Binds views to component instances |
| `ports` | `ipxact:ports` | Container for all port declarations |
| `wire` | `ipxact:wire` | Scalar / vector ports (clk, rst_n, data buses) |
| `structured` | `ipxact:structured` | Composite struct/union ports (pipeline bundles) |
| `adHocConnections` | `ipxact:adHocConnections` | Point-to-point routing between ports |
| `adHocConnection` | `ipxact:adHocConnection` | A single named connection between two port references |
| `typeDefinitions` | `ipxact:typeDefinitions` | Centralized struct/type definition document |
| `structPortTypeDef` | `ipxact:structPortTypeDef` | Named struct type in typeDefinitions |
| `componentInstantiation` | `ipxact:componentInstantiation` | Instantiates a component in the design hierarchy |
| `componentInstance` | `ipxact:componentInstance` | A named instance of a component in the design |

### Category 2 — OPTIONAL (flag as INFO in converter; do NOT generate)

These may appear in legacy 2014 documents but are outside Phase 1 scope.

| Element (local name) | Reason Optional |
|---|---|
| `memoryMap` | Useful for CSR modeling but not needed for pipeline wiring |
| `register` | Part of memory map; deferred to later phase |
| `parameters` | Useful for parameterization; excluded to keep Phase 1 lean |
| `moduleParameters` | Same as above |
| `modes` | Useful for privilege-level modeling; deferred |
| `fileSets` | Useful for EDA tool integration; excluded |
| `views` | Related to fileSets; excluded |
| `qualifiers` | Semantic port tags (isClock, isReset); excluded for now |

### Category 3 — EXCLUDED (flag as WARNING in converter; NEVER generate)

These elements are fundamentally incompatible with the lean point-to-point profile.

| Element (local name) | Reason Excluded |
|---|---|
| `busInterfaces` | Bus abstractions are irrelevant for direct P2P connections |
| `busInterface` | Same |
| `busDefinition` | Defines logical bus protocols — not applicable |
| `abstractionDefinition` | Protocol-level abstraction — not needed |
| `interconnections` | Only links bus interfaces — replaced by adHocConnections |
| `interconnection` | Same |
| `addressSpaces` | Memory-mapped addressing — not used in pipeline stages |
| `addressSpace` | Same |
| `memoryRemap` | Legacy memory remap — irrelevant |
| `transparentBridges` | Passive transaction routing — not applicable |
| `channels` | Multi-point switched routing — overkill for P2P |

---

## 4. Directory Layout

```
arch/ipxact-2022-refdesign/
├── GEMINI.md                              ← You are here
├── docs/
│   └── converter_usage.md                ← How to use the converter CLI
├── skills/
│   └── ipxact-generator/                 ← Gemini Skill for XML generation
│       ├── SKILL.md                      ← ACTIVATE THIS for generation tasks
│       ├── references/
│       │   ├── category1_elements.md
│       │   ├── xml_patterns.md
│       │   └── validation_checklist.md
│       └── examples/
│           └── simple_pipeline.xml
├── src/
│   └── tools/
│       ├── converter/                     ← ipxact-convert CLI
│       │   ├── cli.py
│       │   ├── converter.py
│       │   └── element_categories.py
│       └── validator/                     ← ipxact-validate CLI
│           ├── cli.py
│           ├── validator.py
│           └── schemas/                   ← XSD cache (gitignored)
├── examples/
│   └── sample_2014_input.xml             ← Test input for converter
└── pyproject.toml                         ← uv project config
```

---

## 5. Coding Conventions

- **Package manager**: `uv` exclusively. Never use `pip` directly.
- **Python version**: 3.11+
- **Type hints**: Required on all function signatures. Code must be `mypy`-clean.
- **XML parsing**: Use `lxml` exclusively. Never use `xml.etree.ElementTree`.
- **CLI**: `argparse` for all CLI entrypoints.
- **Error handling**: Fail fast with explicit exceptions. No silent failures.
- **Constants**: All magic strings/values at module top or in `element_categories.py`.
- **One class per file**: Enforce single-responsibility per module.
- **Docstrings**: All public functions and classes must have docstrings.
- **Logging**: Use `stderr` for warnings/errors. `stdout` for structured output only.

---

## 6. Skills Available in This Project

### `skills/ipxact-generator/` — IP-XACT 2022 Generator Skill

**Activate when**: The user asks to generate, create, or produce an IP-XACT 2022 document,
or describes a set of IP stages/units to be modeled.

**What it does**:
1. Reads `references/category1_elements.md` and `references/xml_patterns.md`
2. Interprets the user's natural-language IP description
3. Generates Category-1-only IP-XACT 2022 XML files (typeDefinitions, components, design)
4. Runs `uv run ipxact-validate <file>` to validate against the 2022 XSD
5. Fixes any validation errors before completing

**Hard constraints**:
- Vendor MUST be `saiti`
- Namespace MUST be `http://www.accellera.org/XMLSchema/IPXACT/1685-2022`
- NEVER emit Category 2 or Category 3 elements
- ALWAYS include `clk` and `rst_n` wire ports in every component

---

## 7. CLI Quick Reference

```bash
# Install dependencies
uv sync

# Convert a 2014 IP-XACT file to 2022 (with category flagging)
uv run ipxact-convert --input <input_2014.xml> --output <output_2022.xml>

# Validate any IP-XACT XML against the official 2022 XSD
uv run ipxact-validate <file.xml>
```

---

## 8. Future Phases (Out of Scope for Phase 1)

- **Phase 2**: Add Category 2 optional elements (memoryMap, parameters, views)
- **Phase 3**: TGI REST API integration for automated RTL generation
- **Phase 4**: UVM testbench generation from IP-XACT structural graph
- **Phase 5**: Formal property (SVA) generation
