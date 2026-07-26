# Converter Usage Guide — `ipxact-convert`

Converts an IP-XACT IEEE 1685-2014 XML file to the modern IEEE 1685-2022 standard.

---

## Setup

```bash
# From the project root, install dependencies with uv
uv sync
```

---

## Basic Usage

```bash
uv run ipxact-convert --input <input_2014.xml> --output <output_2022.xml>
```

### Example

```bash
uv run ipxact-convert \
    --input examples/sample_2014_input.xml \
    --output /tmp/converted_2022.xml
```

---

## Options

| Flag | Short | Default | Description |
|---|---|---|---|
| `--input` | `-i` | *(required)* | Path to the source IP-XACT 2014 XML file |
| `--output` | `-o` | *(required)* | Destination path for the generated 2022 XML file |
| `--vendor` | `-v` | `saiti` | Vendor name to enforce in all `<ipxact:vendor>` tags |

---

## What the Converter Does

In order:

1. **Namespace migration** — Replaces all `1685-2014` namespace URIs with `1685-2022`
2. **Vendor normalization** — Overwrites `<ipxact:vendor>` text to the target vendor (`saiti`)
3. **`isPresent` extraction** — Moves deprecated `<ipxact:isPresent>` elements into
   `<ipxact:vendorExtensions>` with correct Accellera wrapper tags
4. **Category 3 flagging** (stderr `[WARNING]`) — Flags bus-centric elements incompatible
   with the lean profile (e.g., `busInterfaces`, `addressSpaces`, `interconnections`)
5. **Category 2 flagging** (stderr `[INFO]`) — Flags optional elements outside Phase 1 scope
   (e.g., `memoryMap`, `parameters`, `views`)

---

## Understanding the Output

### Stdout
The converted XML is written to the `--output` file.

### Stderr
All progress messages, warnings, and info messages go to **stderr**. Redirect as needed:

```bash
# Suppress all stderr messages
uv run ipxact-convert -i old.xml -o new.xml 2>/dev/null

# Save stderr to a log file
uv run ipxact-convert -i old.xml -o new.xml 2>conversion.log
```

### Example stderr output for `sample_2014_input.xml`

```
[*] Ingesting: 'examples/sample_2014_input.xml'
[*] Normalized 1 <ipxact:vendor> element(s) → 'saiti'
[*] Translated 1 <isPresent> element(s) into Accellera Vendor Extensions
[WARNING][Cat3] <busInterfaces>: EXCLUDED: bus protocol abstractions are incompatible with the lean P2P profile.
[WARNING][Cat3] <busInterface>: EXCLUDED: bus protocol abstractions are incompatible with the lean P2P profile.
[INFO][Cat2]    <memoryMaps>: Optional: container for memoryMap elements.
[INFO][Cat2]    <memoryMap>: Optional: useful for CSR/RF modeling but excluded from Phase 1.
[WARNING] 2 Category 3 element type(s) found — these are incompatible with the lean intra-core profile and should be removed.
[INFO] 2 Category 2 element type(s) found — these are optional and outside Phase 1 scope.
[*] Output written to: '/tmp/converted_2022.xml'
```

---

## Validating the Output

After conversion, validate the result against the official 2022 XSD:

```bash
uv run ipxact-validate /tmp/converted_2022.xml
```

> **Note**: Category 3 elements (e.g., `busInterfaces`) are flagged but NOT removed by the
> converter — they are preserved in the output for traceability. You should remove them manually
> if you intend to use the output in the lean intra-core profile.
