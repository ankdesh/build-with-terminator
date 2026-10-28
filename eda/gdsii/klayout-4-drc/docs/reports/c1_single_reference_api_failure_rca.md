# API failure root cause analysis: single-reference ten-case run

Date: 2026-10-27

Both failed cases received the complete verified API reference. The generated
code did not follow the supplied contract in all places. The evidence supports
partial use of the reference followed by unsupported API use. It cannot show
whether the model consciously ignored an instruction or how it processed it.

This analysis uses saved requests, responses, candidates, execution errors,
and small trusted probes against the installed KLayout 0.30.8 binding. It does
not change candidates, rerun them, send model requests, or change campaign scores.

## 1. Was the API information sent?

Yes. The exact rendered 16,169-character reference occurs once in each failed
case's saved request. Each prompt hash matches its generation manifest.
The reference digest is:

`ad5b7aab61cfeb241a0bbf8188485f49a2629056f325a56e4a2f6593ea8dbac5`

Both generation manifests and reference check records identify runtime 0.30.8,
63 checked call contracts, and 12 checked example groups. Repeating the trusted
reference verification during this analysis passed all of those checks.

| Case | User-message characters | Reported prompt tokens | Response finish reason |
|---|---:|---:|---|
| `m1_s1_iso_01` | 25,332 | 6,827 | `stop` |
| `v1_w1_iso_01` | 25,397 | 6,938 | `stop` |

The messages contain these explicit requirements:

- Use only the call forms in the supplied reference.
- If an operation is not covered, preserve affected geometry and state the limit.
- Do not guess a name, overload, keyword, constant, or return type.

The system message contains the expert-role instruction. The detailed contract
and reference are in the user message. This is a possible prompt-design variable,
but this run does not establish that message placement caused either failure.
The saved payload is complete and the responses ended normally. Provider-side
handling and model attention cannot be established from these artifacts.

## 2. M1 spacing case: invented endpoint call and wrong intermediate type

The candidate stops at line 58:

```python
filtered_violations.insert(ep.first.to_p1())
```

The exception is `AttributeError: 'Edge' object has no attribute 'to_p1'`.

The supplied reference already gives the correct chain:

```python
edge = ep.first       # Edge property
point = edge.p1       # Point property
xy = (point.x, point.y)
```

It states the endpoint properties in the binding rules and call table, and
provides an executable `edge_endpoints` helper using them. The candidate also
uses `e_poly.p1` and `e_poly.p2` correctly later in the same script. It uses the
documented `ep.first`, `ep.second`, `length()`, and three-argument `with_length`
forms. These observations show inconsistent application of available guidance.

There is a second defect in the same statement. Replacing `to_p1()` with `p1`
would pass a Point to `Region.insert`. The reference lists Box, Polygon, Path,
and Region as the supported insertion values. A trusted probe confirms that
inserting a Point fails with a TypeError. A marker-presence check needs a
boolean or retained edge-pair objects; it does not need a Region of endpoints.

The script also contains a later, unreached `repaired_poly.resize(...)` call
at line 91. A trusted probe on `db.Polygon` confirms that this member is absent.
The reference supplies Region `sized` and `size` forms instead. This is an
additional API defect found by inspection and a local probe; it was not a second
recorded campaign failure because execution had already stopped at line 58.

### Independent repair-logic defect

The script proposes outward expansion to fix insufficient spacing. Expansion
toward a neighboring wire reduces the gap. The input rectangles have x ranges
0..160 and 200..360 DBU, with a 40 DBU (10 nm) gap. The required spacing is
72 DBU (18 nm). Expanding both by the proposed 36 DBU would overlap them by
32 DBU (8 nm). A trusted in-memory sizing probe on the input geometry confirms
that this hypothetical expansion joins its two components into one.

This probe illustrates the expansion error; it is not execution of the candidate
past its crash. The candidate's selection logic may select only one component.
Even one 36 DBU expansion toward the neighbor reduces the gap from 40 to 4 DBU.
The rationale's claim that outward growth moves the edges apart is incorrect.
Fixing API calls alone would therefore not establish a valid spacing repair.

The prompt includes the complete decoded spacing expression. The candidate
approximates its filtering with edge-length tests and computes an unused
`long_edges` result. Equivalence to the deck was not established.

## 3. V1 width case: geometry value confused with a Shape handle

The candidate stops at line 42:

```python
for poly_with_props in v1_region.each_merged():
    poly = poly_with_props.polygon
```

The exception is `AttributeError: 'PolygonWithProperties' object has no attribute
'polygon'`.

The reference states that `each_merged()` returns PolygonWithProperties objects
and that these support the listed base geometry reads. It separately defines
`shape.polygon` as access through a Shape handle. Its replacement example uses
the returned polygon directly, without an unwrap step.

The correct form is:

```python
for poly in v1_region.each_merged():
    if poly.is_box():
        bbox = poly.bbox()
```

A trusted probe confirms that the returned object is a `db.Polygon` instance
and directly supports `is_box()`, `bbox()`, and `area()`. Access to `.polygon`
fails. The likely mechanism is confusion between a Shape handle and a polygon
value; the model's internal reason cannot be proved.

The reference could make this distinction more explicit. It does not contain
a direct warning that PolygonWithProperties is already a polygon and has no
`.polygon` unwrap property. Correct information was present, but the specific
wrong form was not in the known-error table.

## 4. Why did reference verification not prevent the failures?

Reference verification checks the trusted examples and call contracts against
the candidate runtime. It also checks that compatible reference text is sent.
It does not constrain arbitrary Python emitted by the model.

Candidate response validation checks the JSON fields. Candidate execution then
detects unsupported APIs inside Bubblewrap. This is the designed boundary of
the current single-attempt experiment. There is no general API type checker or
automatic repair loop in this change.

Both candidates reproduce the reference's grid-conversion helper. The spacing
candidate follows several documented call forms and later uses the very endpoint
properties it failed to use at line 58. This is evidence of partial adherence.
The two errors do not support a claim that the whole reference was absent or
ignored. One run also cannot establish whether a longer prompt, model choice,
or instruction placement caused the unsupported calls.

## 5. Recommended next changes

1. Add explicit contrast examples to the canonical reference: Shape handles use
   `.polygon`; polygons from Region iteration are used directly. Add
   `Edge.to_p1()` and `Polygon.resize()` to its known-error table. Verify the
   replacement forms and keep the reference within its size bound.
2. Add a short instruction to trace each expression's input and return types
   against the reference before returning the candidate. This targets the
   Edge-to-Point-to-Region mismatch, as well as nonexistent members. It remains
   a model instruction, not an enforcement mechanism.
3. Add a concise spacing example that increases separation while retaining
   separate components. State that growth into the gap reduces spacing. Check
   geometry and deck semantics separately from API validity.
4. If API validity must be enforced, consider a separate design in which the
   model selects operations and parameters from trusted executable helpers.
   Free-form Python plus documentation cannot enforce the listed API contract.
   This would change the current design and is not implemented by this RCA.

No prompt or source change was made during this analysis. These recommendations
need local verification before any further paid comparison.

## Evidence locations

All case paths below are relative to
`reports/runs/c1_bedrock_pilot10_single_reference_20261027/runs/`:

- `m1_s1_iso_01_20261027_220041_ac4205/`
- `v1_w1_iso_01_20261027_220049_32072f/`

Each contains `model_request.json`, `model_response.json`,
`generation_manifest.json`, `api_reference_check.json`, `candidate_fix.py`,
`candidate_stderr.log`, `rationale.txt`, and `input.gds`.

Guidance and dispatch sources:

- `knowledge/klayout_api_patterns.md`: binding rules, call tables, helpers.
- `src/klayout_drc/api_reference.py`: canonical contract and executable checks.
- `harness/profile/catalog/flows/generate_fix.md`: generation requirements.
- `harness/scripts/api-reference.mjs`: pre-dispatch reference verification.
- `harness/scripts/baseline-contract.mjs`: payload and response-schema handling.
