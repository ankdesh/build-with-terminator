# ipxact-tools

IP-XACT 2022 lean-profile tooling for intra-core IP modeling.

See [GEMINI.md](GEMINI.md) for the project constitution and full documentation.

## Quick Start

```bash
uv sync
uv run ipxact-convert --input examples/sample_2014_input.xml --output /tmp/out.xml
uv run ipxact-validate /tmp/out.xml
```
