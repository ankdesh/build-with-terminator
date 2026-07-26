# Validation Checklist

Run through this checklist **before** calling `ipxact-validate` to catch obvious
errors early and reduce tool round-trips.

---

## Pre-flight Checks (Do These Mentally Before Writing Files)

### Namespace & Structure
- [ ] Root element uses exactly: `xmlns:ipxact="http://www.accellera.org/XMLSchema/IPXACT/1685-2022"`
- [ ] `xsi:schemaLocation` points to the 2022 schema URL
- [ ] XML declaration `<?xml version="1.0" encoding="UTF-8"?>` is present
- [ ] Every root document has `vendor`, `library`, `name`, `version` as first 4 children

### Vendor Identity
- [ ] Every `<ipxact:vendor>` element contains exactly `saiti` (lowercase)

### Component Files
- [ ] Every component has a `<ipxact:ports>` section
- [ ] Every component has `clk` port (wire, direction=in, scalar)
- [ ] Every component has `rst_n` port (wire, direction=in, scalar)
- [ ] No `busInterface` / `busInterfaces` elements present
- [ ] No `addressSpace` / `addressSpaces` elements present
- [ ] No `memoryMap` / `memoryMaps` elements present
- [ ] No `interconnection` / `interconnections` elements present
- [ ] Wire port directions are `in`, `out`, or `inout` (lowercase)
- [ ] `<ipxact:vectors>/<ipxact:vector>` has both `<left>` and `<right>` children
- [ ] Structured ports have `<ipxact:direction>` as first child
- [ ] All subPorts have a `<ipxact:name>` and a `<ipxact:wire>` child

### Design File
- [ ] All `componentInstance/instanceName` values are unique
- [ ] All `componentRef` attributes (vendor, library, name, version) match actual component VLNVs
- [ ] Every `adHocConnection` has a unique `<ipxact:name>`
- [ ] `internalPortReference` uses `componentRef` = instance name (NOT component name)
- [ ] `portRef` values match actual port names defined in the referenced component
- [ ] `clk` and `rst_n` connections broadcast from `externalPortReference` to all instances
- [ ] No orphaned instances (every instance has at least clk/rst_n connections)

### Cross-file Consistency
- [ ] Port names referenced in `adHocConnections` exist in the connected component's `<ipxact:ports>`
- [ ] Structured port field names used in `subPortReference` match subPort names in the component

---

## Final Step: Run the Validator Tool

After all files pass the pre-flight checklist above, validate each file:

```bash
uv run ipxact-validate <output_dir>/type_definitions.xml
uv run ipxact-validate <output_dir>/<stage>_component.xml
uv run ipxact-validate <output_dir>/top_design.xml
```

- **Exit 0** → ✅ Valid. Proceed.
- **Exit 1** → ❌ Invalid. Read the stderr error messages. Each error includes:
  - Line number
  - Error type
  - Description

Fix each error, re-write the file, and re-run until all exit 0.

---

## Common Mistakes to Avoid

| Mistake | Fix |
|---|---|
| Using namespace `1685-2014` | Change all to `1685-2022` |
| Vendor is `saiti` with capital S | Must be lowercase: `saiti` |
| Missing `clk` or `rst_n` port | Add them to every component |
| `componentRef` using component name instead of instance name | Use `instanceName` value |
| Wire direction values capitalized (`In`, `OUT`) | Must be lowercase: `in`, `out`, `inout` |
| `<vector>` missing `<left>` or `<right>` | Add both bounds |
| `adHocConnection` referencing a port that doesn't exist | Check spelling against component's port list |
| Cat 3 elements present (busInterface etc.) | Remove them entirely |
