---
name: ipxact-generator
description: >
  Generate IP-XACT IEEE 1685-2022 XML documents for point-to-point IP modeling
  using the lean intra-core profile (Category 1 elements only). Activate this
  skill when the user asks to generate, create, or produce an IP-XACT 2022 document,
  or describes a set of IP stages or units to be modeled without bus interfaces.
---

# IP-XACT 2022 Generator Skill

This skill produces valid IP-XACT 2022 XML documents using the **lean intra-core
profile** — Category 1 elements only, no bus interfaces, no interconnections.

---

## When to Activate

Activate this skill when the user says things like:
- "Generate an IP-XACT document for..."
- "Create an IP-XACT 2022 file for a pipeline with..."
- "Model these IP stages in IP-XACT..."
- "Write IP-XACT XML for [some hardware description]"

---

## Pre-Generation: Required Reading

**Before writing any XML, you MUST read these reference files:**

1. [`references/category1_elements.md`](references/category1_elements.md) — The complete
   list of allowed elements, their required attributes, and forbidden constructs.

2. [`references/xml_patterns.md`](references/xml_patterns.md) — Copy-paste quality XML
   snippets for every Category 1 element. Use these as your templates.

3. [`examples/simple_pipeline.xml`](examples/simple_pipeline.xml) — A complete, valid
   reference example for a 2-stage IF→ID pipeline. Study the structure.

---

## Generation Workflow

Follow these steps **in order** for every generation request:

### Step 1 — Extract the IP Description

From the user's description, identify:
- **Component names** (e.g., "IF stage", "ID stage", "EX unit") → one component per stage
- **Port names and types** — infer from the description, use sensible defaults:
  - Every component MUST have: `clk` (wire, in), `rst_n` (wire, in, active-low)
  - Pipeline outputs → structured port with a descriptive bundle name (e.g., `if_id_bundle`)
  - Pipeline inputs → structured port matching the upstream output type
- **Connection topology** — which output port connects to which input port

If any information is missing or ambiguous, make sensible hardware-engineering defaults
(add a note in a comment explaining the assumption).

### Step 2 — Plan the Output Files

For a pipeline with N stages, generate these files in the output directory:
```
<output_dir>/
├── type_definitions.xml          ← shared struct types (typeDefinitions document)
├── <stage_name>_component.xml    ← one per component (component document)
└── top_design.xml                ← the wiring document (design document)
```

### Step 3 — Generate `type_definitions.xml`

Write the `ipxact:typeDefinitions` document first. Define one `ipxact:structPortTypeDef`
for each unique pipeline bundle type inferred from the description.

Use the pattern from `references/xml_patterns.md` → Section "typeDefinitions".

**Hard rules:**
- Namespace: `http://www.accellera.org/XMLSchema/IPXACT/1685-2022`
- Vendor: `saiti`
- Include at minimum: a 32-bit `instruction_t` struct with fields `pc`, `raw_instr`

### Step 4 — Generate Component Files

For each stage/unit, write `<stage_name>_component.xml`:
- Use `ipxact:component` as root
- Include `ipxact:ports` with:
  - `clk`: wire, in, 1 bit
  - `rst_n`: wire, in, 1 bit (active-low reset)
  - Pipeline input port (if not first stage): `ipxact:structured`, direction `in`
  - Pipeline output port (if not last stage): `ipxact:structured`, direction `out`
- Include `ipxact:componentInstantiation` block
- **NEVER include** busInterfaces, addressSpaces, interconnections, or any Cat 3 element

Use the patterns from `references/xml_patterns.md` → Sections "component" and "ports".

### Step 5 — Generate `top_design.xml`

Write the `ipxact:design` document:
- Instantiate all components as `ipxact:componentInstance` children
- Wire them together using `ipxact:adHocConnections`
- Each connection references ports by instance name and port name
- `clk` and `rst_n` are broadcast from a single top-level source to all instances

Use the pattern from `references/xml_patterns.md` → Section "design and adHocConnections".

### Step 6 — Write Files to Disk

Write each XML file to the output directory. Use `write_to_file` tool.
Ensure all files use UTF-8 encoding and include the XML declaration:
```xml
<?xml version="1.0" encoding="UTF-8"?>
```

### Step 7 — Validate via Tool

After writing ALL files, run the validator tool on each generated XML file:

```bash
uv run ipxact-validate <output_dir>/type_definitions.xml
uv run ipxact-validate <output_dir>/<stage>_component.xml   # for each component
uv run ipxact-validate <output_dir>/top_design.xml
```

Use `run_command` to execute these. The tool exits 0 for valid, 1 for invalid.
If any file fails (exit code 1), read the error messages from stderr, fix the XML,
re-write the file, and re-run the validator until all files exit 0.

### Step 8 — Report to User

Once all files validate (exit 0), summarize:
- Files generated and their paths
- Components modeled and their ports
- Connections wired in the design
- Any assumptions made about missing information

---

## Hard Rules (NEVER Violate)

| Rule | Value |
|---|---|
| Namespace URI | `http://www.accellera.org/XMLSchema/IPXACT/1685-2022` |
| Vendor | `saiti` |
| Always include | `clk` (wire, in) and `rst_n` (wire, in) in every component |
| Forbidden elements | See Category 3 in `references/category1_elements.md` |
| No bus interfaces | NEVER use busInterface, busDefinition, interconnection |
| No address spaces | NEVER use addressSpace, memoryRemap |
| No memory maps | NEVER use memoryMap or register (Phase 1 scope) |

---

## Validation Checklist

Before calling the validator tool, mentally run through
`references/validation_checklist.md` to catch obvious errors early.
