"""Fetch public source snapshots and prepare the four tutorial CSVs."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "tutorials"
CACHE = ROOT / "data" / "tutorial_sources"
SOURCES = {
    "penguins": {"url": "https://raw.githubusercontent.com/allisonhorst/palmerpenguins/main/inst/extdata/penguins.csv", "page": "https://allisonhorst.github.io/palmerpenguins/", "license": "CC0-1.0", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/", "citation": "Horst, Hill and Gorman (2020), palmerpenguins; observations by Kristen Gorman and Palmer Station LTER.", "file": "penguins.csv"},
    "retail": {"url": "https://archive.ics.uci.edu/static/public/352/online+retail.zip", "page": "https://archive.ics.uci.edu/dataset/352/online+retail", "license": "CC-BY-4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/", "citation": "Chen, D. (2015). Online Retail. UCI Machine Learning Repository. DOI: 10.24432/C5BW33.", "file": "retail.zip"},
    "wine": {"url": "https://archive.ics.uci.edu/static/public/186/wine+quality.zip", "page": "https://archive.ics.uci.edu/dataset/186/wine+quality", "license": "CC-BY-4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/", "citation": "Cortez, Cerdeira, Almeida, Matos and Reis (2009). Wine Quality. UCI. DOI: 10.24432/C56S3T.", "file": "wine.zip"},
    "bike": {"url": "https://archive.ics.uci.edu/static/public/275/bike+sharing+dataset.zip", "page": "https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset", "license": "CC-BY-4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/", "citation": "Fanaee-T, H. (2013). Bike Sharing. UCI Machine Learning Repository. DOI: 10.24432/C5W894.", "file": "bike.zip"},
}
FILES = {"penguins": "penguins.csv", "retail": "retail_q1_2011.csv", "wine": "wine_quality.csv", "bike": "bike_daily.csv"}
DICTIONARIES = {
    "penguins": {
        "species": "Penguin species; categorical group.", "island": "Sampling island in the Palmer Archipelago.",
        "bill_length_mm": "Bill length, millimetres.", "bill_depth_mm": "Bill depth, millimetres.",
        "flipper_length_mm": "Flipper length, millimetres.", "body_mass_g": "Body mass, grams.",
        "sex": "Recorded sex; missing values remain in the supplied CSV.", "year": "Observation year, not a complete time series.",
    },
    "retail": {
        "InvoiceNo": "Invoice identifier; a C prefix marks cancellation. Read as text.", "StockCode": "Item identifier; includes non-product charge codes. Read as text.",
        "Description": "Source item description; may be missing.", "Quantity": "Units on this invoice line; negative values can represent returns.",
        "InvoiceDate": "Source invoice date and time, normalized to ISO text; no timezone is supplied.",
        "UnitPrice": "Price per unit in pounds sterling (GBP).", "CustomerID": "Customer identifier as text; missing IDs must not remove valid sales.",
        "Country": "Customer country. Results are historical, not current market figures.",
    },
    "wine": {
        "fixed acidity": "Fixed acidity, g/dm³ as tartaric acid.", "volatile acidity": "Volatile acidity, g/dm³ as acetic acid.",
        "citric acid": "Citric acid, g/dm³.", "residual sugar": "Residual sugar, g/dm³.", "chlorides": "Chlorides, g/dm³ as sodium chloride.",
        "free sulfur dioxide": "Free sulfur dioxide, mg/dm³.", "total sulfur dioxide": "Total sulfur dioxide, mg/dm³.",
        "density": "Density, g/cm³.", "pH": "pH; dimensionless.", "sulphates": "Sulphates, g/dm³ as potassium sulphate.",
        "alcohol": "Alcohol, percent by volume.", "quality": "Ordered sensory score from 0 to 10; not a percentage.",
        "wine_type": "Source CSV: red or white. Added when joining the two public files.",
    },
    "bike": {
        "instant": "Source row identifier.", "dteday": "Calendar date; one row per day.", "season": "Publisher's season codes: 1 spring, 2 summer, 3 fall, 4 winter. These are source labels.",
        "yr": "Year code: 0 means 2011; 1 means 2012.", "mnth": "Calendar month, 1–12.", "holiday": "Publisher's holiday flag, 0 or 1.",
        "weekday": "Weekday code, Sunday 0 through Saturday 6.", "workingday": "1 for a weekday that is not a holiday.",
        "weathersit": "Weather code: 1 clear/few/partly cloudy; 2 mist with cloud; 3 light rain or snow; 4 heavy rain/ice, snow or fog. Source categories, not measured precipitation.",
        "temp": "Normalized temperature. Dimensionless; do not label these values °C.",
        "atemp": "Normalized apparent temperature. Dimensionless.", "hum": "Normalized relative humidity; multiply by 100 for percent.",
        "windspeed": "Normalized wind speed; retain normalized units in this lesson.",
        "casual": "Daily rentals by casual users.", "registered": "Daily rentals by registered users.", "cnt": "Total daily rentals; casual plus registered.",
    },
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(item: tuple[str, dict]) -> tuple[str, Path, str]:
    key, source = item
    path = CACHE / source["file"]
    stamp = path.with_suffix(path.suffix + ".json")
    if not path.exists():
        print(f"Downloading public {key} data", flush=True)
        request = urllib.request.Request(source["url"], headers={"User-Agent": "WPS-AI educational tutorial preparation"})
        with urllib.request.urlopen(request, timeout=120) as response:
            content = response.read()
        path.write_bytes(content)
        stamp.write_text(json.dumps({"retrieved_at": datetime.now(timezone.utc).isoformat(), "sha256": sha(path)}))
    metadata = json.loads(stamp.read_text())
    if sha(path) != metadata["sha256"]:
        raise ValueError(f"Cached source hash changed: {path}")
    return key, path, metadata["retrieved_at"]


def archive_file(path: Path, filename: str) -> bytes:
    with zipfile.ZipFile(path) as archive:
        member = next(name for name in archive.namelist() if Path(name).name == filename)
        return archive.read(member)


def prepare() -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    (PACK / "data").mkdir(parents=True, exist_ok=True)
    (PACK / "practice").mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        snapshots = {key: (path, date) for key, path, date in pool.map(fetch, SOURCES.items())}
    frames = {"penguins": pd.read_csv(snapshots["penguins"][0])}
    retail = pd.read_excel(io.BytesIO(archive_file(snapshots["retail"][0], "Online Retail.xlsx")), engine="openpyxl")
    dates = pd.to_datetime(retail["InvoiceDate"])
    retail = retail.loc[(dates >= "2011-01-01") & (dates < "2011-04-01")].copy()
    retail["InvoiceDate"] = pd.to_datetime(retail["InvoiceDate"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    for name in ("InvoiceNo", "StockCode", "CustomerID"):
        retail[name] = retail[name].map(lambda value: "" if pd.isna(value) else str(int(value)) if isinstance(value, (int, float)) and float(value).is_integer() else str(value))
    frames["retail"] = retail
    frames["wine"] = pd.concat([pd.read_csv(io.BytesIO(archive_file(snapshots["wine"][0], f"winequality-{kind}.csv")), sep=";").assign(wine_type=kind) for kind in ("red", "white")], ignore_index=True)
    frames["bike"] = pd.read_csv(io.BytesIO(archive_file(snapshots["bike"][0], "day.csv")))
    replacements = {
        "penguins": frames["penguins"].loc[frames["penguins"]["species"] == "Gentoo"],
        "retail": retail.loc[retail["InvoiceDate"].str.startswith("2011-03")],
        "wine": frames["wine"].loc[frames["wine"]["wine_type"] == "red"],
        "bike": frames["bike"].loc[frames["bike"]["yr"] == 1],
    }
    removed = {"penguins": "body_mass_g", "retail": "UnitPrice", "wine": "alcohol", "bike": "cnt"}
    transformations = {
        "penguins": "Normalize CSV encoding and missing tokens to empty cells. Preserve all source observations.",
        "retail": "Convert Excel to CSV; retain all rows from 2011-01-01 inclusive to 2011-04-01 exclusive in source order. Normalize dates to ISO and identifiers to text. No analytical cleaning.",
        "wine": "Read both semicolon-separated CSVs, append wine_type=red/white, concatenate red then white, and write comma-separated CSV. Preserve repeated observations.",
        "bike": "Use day.csv, not hour.csv. Normalize CSV encoding; keep source values, dates, normalized weather variables, and codes.",
    }
    manifest = {"schema_version": 1, "datasets": {}}
    for key, frame in frames.items():
        path = PACK / "data" / FILES[key]
        frame.to_csv(path, index=False, lineterminator="\n")
        replacement = PACK / "practice" / f"{key}_replacement.csv"
        replacements[key].to_csv(replacement, index=False, lineterminator="\n")
        invalid = PACK / "practice" / f"{key}_invalid_schema.csv"
        replacements[key].head(20).drop(columns=[removed[key]]).to_csv(invalid, index=False, lineterminator="\n")
        source_path, retrieved = snapshots[key]
        manifest["datasets"][key] = {**SOURCES[key], "file": f"data/{FILES[key]}", "sha256": sha(path),
            "source_sha256": sha(source_path), "retrieved_at": retrieved, "rows": len(frame), "columns": list(frame.columns),
            "missing_cells": {name: int((frame[name].isna() | frame[name].eq("")).sum()) for name in frame.columns},
            "repeated_rows": int(frame.duplicated().sum()), "transformation": transformations[key], "dictionary": DICTIONARIES[key],
            "practice": {"replacement": str(replacement.relative_to(PACK)), "rows": len(replacements[key]),
                         "invalid": str(invalid.relative_to(PACK)), "removed_column": removed[key],
                         "replacement_sha256": sha(replacement), "invalid_sha256": sha(invalid)}}
        print(f"Prepared {key}: {len(frame):,} rows; {path.stat().st_size:,} bytes", flush=True)
    (PACK / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    attribution = ["PUBLIC DATA SOURCES — WPS-AI tutorial pack", "", "CSV transformations are described in manifest.json. These are historical public observations, not synthetic records.", ""]
    for key, source in SOURCES.items():
        attribution += [key.upper(), source["citation"], source["page"], f"Licence: {source['license']} — {source['license_url']}", transformations[key], ""]
    (PACK / "ATTRIBUTION.txt").write_text("\n".join(attribution), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    prepare()
