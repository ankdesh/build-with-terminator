# C1 dataset release 1.1.0

This release preserves all 100 v1 case GDS files and their hashes. It contains
93 distinct layouts, 78 dirty entries, and 22 clean controls. Duplicate layouts
remain as named entries for historical comparison. Use `duplicate_group` for
results on distinct layouts.

The checker scope is `asap7_curated`, with five categories: M1.W.1, M2.W.1,
M1.A.1, M1.S.1, and V1.W.1. V1.W.1 checks minimum width, not a square-cut rule.
Enclosure coverage from the original Phase B proposal was replaced by via width.
This release makes no enclosure or full-deck compliance claim.

`references/` contains synthetic checker-clean component seeds. These are new
legal references, not recovered pristine layouts. Each seed retains the layers
and number of connected geometric components. Rectangular legal components are
placed apart. The manifest stores exact integer-region additions and removals
that map each seed to its original case. Mutation round trips are checked.

`oracle/` contains actual before-case and reference checker databases. The
manifest records expected categories and totals from the frozen catalog,
calibrated per-rule counts, observed markers, file hashes, constructor geometry,
checker identity, and component-preservation constraints. Generation rejects a
category/total mismatch or a reference with any scoped violation. Evaluation
checks hashes and then compares a fresh baseline with the accepted counts and
markers before synthesis.

All current case geometry is editable. No immutable spatial regions are declared
for these small synthetic cases. The evaluator supports explicit protected
regions and protects child masters and their instance definitions. Component
counts catch simple erasure and merging shortcuts; they do not prove net
connectivity or correspondence. Validation remains `geometry_only`.

The generator uses a fixed catalog, not random sampling. Repeated generation
must reproduce GDS hashes, marker data, and manifest metadata apart from the
publication timestamp. Stage logs contain elapsed times and are not part of
this stable metadata comparison.

Keep this manifest, references, mutation records, and oracle expectations outside
model inputs. The model receives only checker observations, decoded active
rules, local geometry, profile facts, and the frozen API/repair guidance.
