# Category 1 — Mandatory Elements Reference

This document is the authoritative specification for elements permitted in
IP-XACT 2022 lean-profile documents. **Only these elements may appear.**

---

## Namespace

All elements use this namespace URI:
```
http://www.accellera.org/XMLSchema/IPXACT/1685-2022
```

XML prefix convention: `ipxact:`

---

## Mandatory Elements Table

| Local Name | XML Tag | Role | Required Children / Attributes |
|---|---|---|---|
| `component` | `ipxact:component` | Atomic IP block definition | `vendor`, `library`, `name`, `version`, `ports`, `componentInstantiation` |
| `design` | `ipxact:design` | Top-level structural wiring | `vendor`, `library`, `name`, `version`, `componentInstances`, `adHocConnections` |
| `designConfiguration` | `ipxact:designConfiguration` | Binds views to instances | `vendor`, `library`, `name`, `version` |
| `ports` | `ipxact:ports` | Port container | One or more `port` children |
| `port` | `ipxact:port` | Individual port | `name`, then either `wire` or `structured` |
| `wire` | `ipxact:wire` | Scalar / vector signal | `direction` (in/out/inout); optionally `vectors` |
| `vectors` | `ipxact:vectors` | Bit-width of a wire | `vector` child with `left` and `right` bounds |
| `vector` | `ipxact:vector` | Individual vector range | `left`, `right` (e.g., `<left>7</left><right>0</right>` for 8 bits) |
| `structured` | `ipxact:structured` | Composite struct/union port | `direction`, `typeDefinitionRef` (or inline `subPort` list) |
| `subPort` | `ipxact:subPort` | Field within a structured port | `name`, `wire` (with direction and vectors) |
| `adHocConnections` | `ipxact:adHocConnections` | Connection container | One or more `adHocConnection` children |
| `adHocConnection` | `ipxact:adHocConnection` | A single point-to-point connection | `name`, `portReferences` |
| `internalPortReference` | `ipxact:internalPortReference` | References a port on an instance | `componentRef`, `portRef` |
| `externalPortReference` | `ipxact:externalPortReference` | References a port on the design boundary | `portRef` |
| `subPortReference` | `ipxact:subPortReference` | Slices a specific field in a structured port | `portRef`, `subPortRef` |
| `typeDefinitions` | `ipxact:typeDefinitions` | Centralized type library document | `vendor`, `library`, `name`, `version`, `structPortTypeDef` list |
| `structPortTypeDef` | `ipxact:structPortTypeDef` | Named struct type | `name`, `displayName`, `subPort` list |
| `componentInstantiation` | `ipxact:componentInstantiation` | View binding inside a component | `name` |
| `componentInstance` | `ipxact:componentInstance` | Named instance in the design | `instanceName`, `componentRef` |

---

## VLNV Tuple (Required on Every Root Document)

Every root element (`component`, `design`, `designConfiguration`, `typeDefinitions`) MUST
include the VLNV (Vendor-Library-Name-Version) tuple as direct children:

```xml
<ipxact:vendor>saiti</ipxact:vendor>
<ipxact:library>lean_core</ipxact:library>
<ipxact:name>my_component_name</ipxact:name>
<ipxact:version>1.0</ipxact:version>
```

- `vendor` is ALWAYS `saiti`
- `library` is typically `lean_core` for Phase 1
- `name` is the descriptive name of the document
- `version` is `1.0` unless specified otherwise

---

## Port Direction Values

| Value | Meaning |
|---|---|
| `in` | Input to this component |
| `out` | Output from this component |
| `inout` | Bidirectional |

---

## Forbidden Elements (Category 3 — NEVER USE)

These elements MUST NEVER appear in generated documents:

| Element | Why Forbidden |
|---|---|
| `busInterface` / `busInterfaces` | Requires bus protocol definitions — not applicable |
| `busDefinition` | Defines logical bus signals — not used in P2P profile |
| `abstractionDefinition` | Protocol abstraction layer — excluded |
| `interconnection` / `interconnections` | Connects bus interfaces only — replaced by adHocConnections |
| `addressSpace` / `addressSpaces` | Memory-mapped addressing — not applicable |
| `memoryRemap` / `memoryRemaps` | Dynamic memory remapping — not applicable |
| `transparentBridge` / `transparentBridges` | Passive transaction routing — not applicable |
| `channel` / `channels` | Multi-point switched routing — not needed |

---

## Outside Phase 1 Scope (Category 2 — Do Not Generate)

These elements are valid in 2022 but excluded from Phase 1:

`memoryMap`, `register`, `field`, `parameters`, `moduleParameters`,
`modes`, `fileSets`, `views`, `qualifiers`, `isClock`, `isReset`
