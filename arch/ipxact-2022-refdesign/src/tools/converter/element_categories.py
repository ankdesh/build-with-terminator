"""
element_categories.py
=====================
Canonical registry of IP-XACT 2022 element categories for the lean intra-core profile.

Category 1 — Mandatory: Only these elements are used in the lean profile.
Category 2 — Optional:  Present in legacy 2014 docs; flag as INFO during conversion.
Category 3 — Excluded:  Bus-centric constructs; flag as WARNING during conversion.

All sets contain XML local names (without namespace prefix).
"""

# ---------------------------------------------------------------------------
# Category 1 — MANDATORY elements for the lean intra-core profile
# ---------------------------------------------------------------------------
CATEGORY_1_ELEMENTS: frozenset[str] = frozenset({
    "component",
    "design",
    "designConfiguration",
    "ports",
    "port",
    "wire",
    "vectors",
    "vector",
    "structured",
    "subPort",
    "adHocConnections",
    "adHocConnection",
    "internalPortReference",
    "externalPortReference",
    "subPortReference",
    "typeDefinitions",
    "structPortTypeDef",
    "componentInstantiation",
    "componentInstance",
    "instanceName",
    "vendor",
    "library",
    "name",
    "version",
})

# ---------------------------------------------------------------------------
# Category 2 — OPTIONAL elements (INFO-level flags in converter output)
# ---------------------------------------------------------------------------
CATEGORY_2_ELEMENTS: dict[str, str] = {
    "memoryMap":       "Optional: useful for CSR/RF modeling but excluded from Phase 1.",
    "memoryMaps":      "Optional: container for memoryMap elements.",
    "register":        "Optional: part of memory map; deferred to Phase 2.",
    "registers":       "Optional: container for register elements.",
    "field":           "Optional: register field; deferred to Phase 2.",
    "parameters":      "Optional: parameterization deferred to Phase 2.",
    "parameter":       "Optional: individual parameter; deferred to Phase 2.",
    "moduleParameters":"Optional: module-level parameters; deferred to Phase 2.",
    "moduleParameter": "Optional: individual module parameter; deferred to Phase 2.",
    "modes":           "Optional: privilege/pipeline modes; deferred to Phase 2.",
    "mode":            "Optional: individual mode definition; deferred to Phase 2.",
    "fileSets":        "Optional: EDA tool file pointers; excluded from lean profile.",
    "fileSet":         "Optional: individual file set; excluded from lean profile.",
    "file":            "Optional: HDL source pointer; excluded from lean profile.",
    "views":           "Optional: component views (RTL, TLM, etc.); excluded from lean profile.",
    "view":            "Optional: individual view; excluded from lean profile.",
    "qualifiers":      "Optional: semantic port tags (isClock, isReset); excluded for now.",
    "qualifier":       "Optional: individual port qualifier; excluded for now.",
    "isClock":         "Optional: clock port qualifier; excluded from Phase 1.",
    "isReset":         "Optional: reset port qualifier; excluded from Phase 1.",
    "isInterrupt":     "Optional: interrupt port qualifier; excluded from Phase 1.",
    "isRequest":       "Optional: request port qualifier; excluded from Phase 1.",
    "isResponse":      "Optional: response port qualifier; excluded from Phase 1.",
}

# ---------------------------------------------------------------------------
# Category 3 — EXCLUDED elements (WARNING-level flags in converter output)
# ---------------------------------------------------------------------------
CATEGORY_3_ELEMENTS: dict[str, str] = {
    "busInterfaces":          "EXCLUDED: bus protocol abstractions are incompatible with the lean P2P profile.",
    "busInterface":           "EXCLUDED: bus protocol abstractions are incompatible with the lean P2P profile.",
    "busDefinition":          "EXCLUDED: defines logical bus protocol signals — not applicable for direct wiring.",
    "abstractionDefinition":  "EXCLUDED: protocol-level abstraction layer — not needed for intra-core modeling.",
    "abstractionDefinitions": "EXCLUDED: container for abstractionDefinition elements — not applicable.",
    "interconnections":       "EXCLUDED: connects bus interfaces only — replaced entirely by adHocConnections.",
    "interconnection":        "EXCLUDED: individual bus interconnection — replaced by adHocConnection.",
    "addressSpaces":          "EXCLUDED: memory-mapped address regions — irrelevant for pipeline stages.",
    "addressSpace":           "EXCLUDED: individual address space — irrelevant for pipeline stages.",
    "memoryRemap":            "EXCLUDED: dynamic memory map remapping — not applicable in pipeline context.",
    "memoryRemaps":           "EXCLUDED: container for memoryRemap elements — not applicable.",
    "transparentBridges":     "EXCLUDED: passive transaction routing — pipeline stages do active computation.",
    "transparentBridge":      "EXCLUDED: individual bridge element — pipeline stages do active computation.",
    "channels":               "EXCLUDED: multi-point switched routing — P2P adHocConnections are sufficient.",
    "channel":                "EXCLUDED: individual channel — not needed for point-to-point topology.",
}
