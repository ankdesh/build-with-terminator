WPS-AI Field Guide

Extract the entire ZIP, then open index.html in a desktop browser. All chart scripts and reference data are local. Follow lessons in the builder; reference pages never call its API.

Public source attribution: ATTRIBUTION.txt
Data hashes and transformations: manifest.json
Live model validation: validation.html and validation.json

Regeneration from repository root:
uv pip install -e ".[tutorials]"
python scripts/tutorial_data.py
python scripts/tutorial_validate.py --live-model
python scripts/build_tutorials.py

Live validation uses API tokens and writes isolated projects only under data/tutorial_validation. Matching passed validations are reused.
