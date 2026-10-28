# Geometric repair decisions

Use the single **KLayout Python API: layout repair and hierarchy** reference for
call forms, units, grid conversion, types, mutation behavior, and coordinate
frames. Use the active profile for physical layers and the complete decoded deck
for thresholds and rule conditions. API examples are not technology rules.

## Width and area

Select the violating component from checker markers and local geometry. Limit
edits to permitted boundaries. For an isolated rectangle, increasing its narrow
dimension can fix width; do not treat a general polygon's bounding box as its
minimum width. Check area per component, including holes. A large neighbor does
not make an undersized island legal. Preserve unaffected components and verify
that enlargement does not create spacing, width, area, or grid violations.

## Spacing

Preserve separate components when net ownership is unknown. Do not merge wires
to remove a spacing marker. Use a permitted displacement or boundary change that
preserves the stated component and protected-region constraints. Trimming can
create opens or new width/area violations. The full checker expression controls
edge-length filters, projections, and boundary equality; a generic spacing check
is not automatically equivalent to the decoded rule.

## Enclosure and clean inputs

The curated five-rule ASAP7 profile does not check enclosure. Do not apply a
legacy enclosure example to it. Other profiles must follow all active directional
conditions from their decoded deck.

For a checker-clean input, write the input without changing its geometry. Do not
apply blanket sizing, merging, or enclosure changes. Preserve the immutable
input and write a separate output. A successful geometry check does not establish
electrical validity. State unsupported repairs instead of claiming success.
