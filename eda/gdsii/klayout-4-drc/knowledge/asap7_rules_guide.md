# ASAP7 Process Design Kit (PDK) Rules Guide

This is a profile-scoped guide for {{PROFILE}}. The loader appends the active
layer table, DBU convention, and manufacturing grid from the selected profile.
Use the input layout's actual DBU. Layer numbers in another profile do not apply.

The curated ASAP7 deck checks M1.W.1, M2.W.1, M1.A.1, M1.S.1, and V1.W.1.
M1 and M2 minimum width is 18nm; M1 minimum area is 504nm2. The 18nm M1
spacing check has the edge-length filter shown in its decoded deck expression.
V1.W.1 is a minimum-width check. It does not enforce a square via shape.

The legacy mini profile uses different layer conventions and rule IDs.
Its 9nm enclosure example is not an ASAP7 enclosure specification. Consult all
active public-deck branches for directional enclosure constraints. The current
curated evaluation makes no enclosure claim.

DRC compliance is geometric. Net ownership and electrical connectivity are unknown.
