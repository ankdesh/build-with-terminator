# C2+C3 five-level ASAP7 benchmark

Read `manifest.json` for the accepted case list and completion status. A GDS file
is a benchmark case only when the manifest lists it. Files under `oracle/` are
private evaluator inputs. Do not give them to a model or candidate worker.

The qualified corpus has 50 cases: ten per level. Each level has six repair cases, two
clean controls, and two read-only cases. Controls do not earn repair credit.
Baseline source violations can remain outside a case's declared target scope.
All results are geometry-only. Connectivity and timing are not verified.

Use [CASE_INDEX.md](CASE_INDEX.md) to find full GDS files and local inspection
clips. Source and test receipts are under [provenance/](provenance/README.md).

The `cases/` files preserve real ASAP7 standard-cell geometry. C3 files must
also retain the complete routed block. The manifest records the source and
qualification evidence for each accepted file. `rejections.json` records failed
generation candidates. Rejected files stay outside the published case list.

Use the separate `asap7_c2c3_v1` checker profile. It does not change the C1
checker. Its provenance file records copied public expressions, effective
enclosure boundaries, and the independently tested V2/M2 enclosure correction.

Standard-cell source: OpenROAD ASAP7 `asap7sc7p5t_28_R_220121a.gds`, obtained
from the pinned ORFS platform. Source hashes are in the case records. The cell
library's BSD 3-Clause notice is in `ASAP7-LICENSE.txt`. The source license is
also available at:
https://github.com/The-OpenROAD-Project/asap7sc7p5t_28/blob/f970bd3c3292b79ae4d022a3ec80533534614066/LICENSE

See `docs/C2_C3_BENCHMARK.md` for commands, source pins, policies, and limits.
