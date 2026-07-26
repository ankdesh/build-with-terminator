# IP-XACT 2022 XML Patterns

Annotated, copy-paste-quality XML snippets for each Category 1 element.
Use these as templates when generating documents.

---

## Document Skeleton

Every IP-XACT 2022 document follows this structure:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ipxact:DOCUMENT_TYPE
    xmlns:ipxact="http://www.accellera.org/XMLSchema/IPXACT/1685-2022"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.accellera.org/XMLSchema/IPXACT/1685-2022
                        http://www.accellera.org/XMLSchema/IPXACT/1685-2022/index.xsd">

  <!-- VLNV tuple — always first four children -->
  <ipxact:vendor>saiti</ipxact:vendor>
  <ipxact:library>lean_core</ipxact:library>
  <ipxact:name>DESCRIPTIVE_NAME</ipxact:name>
  <ipxact:version>1.0</ipxact:version>

  <!-- document body here -->

</ipxact:DOCUMENT_TYPE>
```

Replace `DOCUMENT_TYPE` with: `component`, `design`, `designConfiguration`, or `typeDefinitions`.

---

## 1. typeDefinitions Document

Defines shared struct types referenced by multiple components.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ipxact:typeDefinitions
    xmlns:ipxact="http://www.accellera.org/XMLSchema/IPXACT/1685-2022"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.accellera.org/XMLSchema/IPXACT/1685-2022
                        http://www.accellera.org/XMLSchema/IPXACT/1685-2022/index.xsd">

  <ipxact:vendor>saiti</ipxact:vendor>
  <ipxact:library>lean_core</ipxact:library>
  <ipxact:name>pipeline_types</ipxact:name>
  <ipxact:version>1.0</ipxact:version>

  <!-- Define a struct type for the IF→ID pipeline bundle -->
  <ipxact:structPortTypeDef>
    <ipxact:name>if_id_bundle_t</ipxact:name>
    <ipxact:displayName>IF to ID Pipeline Bundle</ipxact:displayName>

    <!-- Program Counter: 32-bit unsigned -->
    <ipxact:subPort>
      <ipxact:name>pc</ipxact:name>
      <ipxact:wire>
        <ipxact:direction>out</ipxact:direction>
        <ipxact:vectors>
          <ipxact:vector>
            <ipxact:left>31</ipxact:left>
            <ipxact:right>0</ipxact:right>
          </ipxact:vector>
        </ipxact:vectors>
      </ipxact:wire>
    </ipxact:subPort>

    <!-- Raw Instruction Bits: 32-bit -->
    <ipxact:subPort>
      <ipxact:name>raw_instr</ipxact:name>
      <ipxact:wire>
        <ipxact:direction>out</ipxact:direction>
        <ipxact:vectors>
          <ipxact:vector>
            <ipxact:left>31</ipxact:left>
            <ipxact:right>0</ipxact:right>
          </ipxact:vector>
        </ipxact:vectors>
      </ipxact:wire>
    </ipxact:subPort>

    <!-- Valid flag: 1-bit -->
    <ipxact:subPort>
      <ipxact:name>valid</ipxact:name>
      <ipxact:wire>
        <ipxact:direction>out</ipxact:direction>
        <!-- No vectors = scalar (1 bit) -->
      </ipxact:wire>
    </ipxact:subPort>

  </ipxact:structPortTypeDef>

</ipxact:typeDefinitions>
```

---

## 2. Component Document

Models one pipeline stage / functional IP unit.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ipxact:component
    xmlns:ipxact="http://www.accellera.org/XMLSchema/IPXACT/1685-2022"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.accellera.org/XMLSchema/IPXACT/1685-2022
                        http://www.accellera.org/XMLSchema/IPXACT/1685-2022/index.xsd">

  <ipxact:vendor>saiti</ipxact:vendor>
  <ipxact:library>lean_core</ipxact:library>
  <ipxact:name>if_stage</ipxact:name>
  <ipxact:version>1.0</ipxact:version>

  <ipxact:ports>

    <!-- Mandatory clock port -->
    <ipxact:port>
      <ipxact:name>clk</ipxact:name>
      <ipxact:wire>
        <ipxact:direction>in</ipxact:direction>
        <!-- scalar: no vectors child needed for 1-bit signals -->
      </ipxact:wire>
    </ipxact:port>

    <!-- Mandatory active-low reset port -->
    <ipxact:port>
      <ipxact:name>rst_n</ipxact:name>
      <ipxact:wire>
        <ipxact:direction>in</ipxact:direction>
      </ipxact:wire>
    </ipxact:port>

    <!-- A 32-bit instruction memory address input (example scalar vector port) -->
    <ipxact:port>
      <ipxact:name>pc_in</ipxact:name>
      <ipxact:wire>
        <ipxact:direction>in</ipxact:direction>
        <ipxact:vectors>
          <ipxact:vector>
            <ipxact:left>31</ipxact:left>
            <ipxact:right>0</ipxact:right>
          </ipxact:vector>
        </ipxact:vectors>
      </ipxact:wire>
    </ipxact:port>

    <!-- Structured output bundle: the full IF→ID pipeline register -->
    <ipxact:port>
      <ipxact:name>if_id_out</ipxact:name>
      <ipxact:structured>
        <ipxact:direction>out</ipxact:direction>
        <!-- Inline subPorts (alternative: use typeDefinitionRef for shared types) -->
        <ipxact:subPort>
          <ipxact:name>pc</ipxact:name>
          <ipxact:wire>
            <ipxact:direction>out</ipxact:direction>
            <ipxact:vectors>
              <ipxact:vector>
                <ipxact:left>31</ipxact:left>
                <ipxact:right>0</ipxact:right>
              </ipxact:vector>
            </ipxact:vectors>
          </ipxact:wire>
        </ipxact:subPort>
        <ipxact:subPort>
          <ipxact:name>raw_instr</ipxact:name>
          <ipxact:wire>
            <ipxact:direction>out</ipxact:direction>
            <ipxact:vectors>
              <ipxact:vector>
                <ipxact:left>31</ipxact:left>
                <ipxact:right>0</ipxact:right>
              </ipxact:vector>
            </ipxact:vectors>
          </ipxact:wire>
        </ipxact:subPort>
        <ipxact:subPort>
          <ipxact:name>valid</ipxact:name>
          <ipxact:wire>
            <ipxact:direction>out</ipxact:direction>
          </ipxact:wire>
        </ipxact:subPort>
      </ipxact:structured>
    </ipxact:port>

  </ipxact:ports>

  <!-- Component instantiation block: links to an RTL view (conceptual) -->
  <ipxact:componentInstantiations>
    <ipxact:componentInstantiation>
      <ipxact:name>rtl</ipxact:name>
    </ipxact:componentInstantiation>
  </ipxact:componentInstantiations>

</ipxact:component>
```

---

## 3. Design Document (with adHocConnections)

The top-level document that instantiates components and wires them together.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ipxact:design
    xmlns:ipxact="http://www.accellera.org/XMLSchema/IPXACT/1685-2022"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.accellera.org/XMLSchema/IPXACT/1685-2022
                        http://www.accellera.org/XMLSchema/IPXACT/1685-2022/index.xsd">

  <ipxact:vendor>saiti</ipxact:vendor>
  <ipxact:library>lean_core</ipxact:library>
  <ipxact:name>cpu_core_top</ipxact:name>
  <ipxact:version>1.0</ipxact:version>

  <!-- Instantiate the IF stage -->
  <ipxact:componentInstances>

    <ipxact:componentInstance>
      <ipxact:instanceName>u_if_stage</ipxact:instanceName>
      <ipxact:componentRef
          vendor="saiti"
          library="lean_core"
          name="if_stage"
          version="1.0"/>
    </ipxact:componentInstance>

    <ipxact:componentInstance>
      <ipxact:instanceName>u_id_stage</ipxact:instanceName>
      <ipxact:componentRef
          vendor="saiti"
          library="lean_core"
          name="id_stage"
          version="1.0"/>
    </ipxact:componentInstance>

  </ipxact:componentInstances>

  <ipxact:adHocConnections>

    <!-- Connect clk from design boundary to both instances -->
    <ipxact:adHocConnection>
      <ipxact:name>clk_net</ipxact:name>
      <ipxact:portReferences>
        <ipxact:externalPortReference portRef="clk"/>
        <ipxact:internalPortReference componentRef="u_if_stage" portRef="clk"/>
        <ipxact:internalPortReference componentRef="u_id_stage" portRef="clk"/>
      </ipxact:portReferences>
    </ipxact:adHocConnection>

    <!-- Connect rst_n from design boundary to both instances -->
    <ipxact:adHocConnection>
      <ipxact:name>rst_n_net</ipxact:name>
      <ipxact:portReferences>
        <ipxact:externalPortReference portRef="rst_n"/>
        <ipxact:internalPortReference componentRef="u_if_stage" portRef="rst_n"/>
        <ipxact:internalPortReference componentRef="u_id_stage" portRef="rst_n"/>
      </ipxact:portReferences>
    </ipxact:adHocConnection>

    <!-- Connect the full IF→ID structured bundle: if_stage output → id_stage input -->
    <ipxact:adHocConnection>
      <ipxact:name>if_id_pipeline_reg</ipxact:name>
      <ipxact:portReferences>
        <ipxact:internalPortReference componentRef="u_if_stage" portRef="if_id_out"/>
        <ipxact:internalPortReference componentRef="u_id_stage" portRef="if_id_in"/>
      </ipxact:portReferences>
    </ipxact:adHocConnection>

    <!-- Example: sub-port reference — route only the 'pc' field from IF to a monitor -->
    <!--
    <ipxact:adHocConnection>
      <ipxact:name>pc_monitor_tap</ipxact:name>
      <ipxact:portReferences>
        <ipxact:internalPortReference componentRef="u_if_stage" portRef="if_id_out">
          <ipxact:subPortReference subPortRef="pc"/>
        </ipxact:internalPortReference>
        <ipxact:externalPortReference portRef="pc_monitor_out"/>
      </ipxact:portReferences>
    </ipxact:adHocConnection>
    -->

  </ipxact:adHocConnections>

</ipxact:design>
```

---

## Key Rules Embedded in Patterns

- `clk` and `rst_n` are ALWAYS present in every component
- Structured ports use inline `subPort` children for Phase 1 (no `typeDefinitionRef` required)
- `adHocConnection` uses `componentRef` to reference instance names (not component names)
- External ports (design boundary) use `externalPortReference`
- Sub-port slicing uses `subPortReference` inside `internalPortReference`
- All `direction` values inside `subPort/wire` must match the parent structured port direction
