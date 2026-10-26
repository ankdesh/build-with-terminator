"""Create and validate a reference project without calling an LLM."""

import asyncio
from pathlib import Path
import sys
import tempfile
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.services.project_store import ProjectStore

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def create_demo(store: "ProjectStore") -> dict[str, Any]:
    from backend.services.data_profiler import DataProfiler
    from backend.services.project_service import ProjectService
    from examples.electric_dashboard import revision
    import pandas as pd
    project = store.create("Energy usage example")
    data = pd.read_csv(ROOT / "sample_data/electric_usage.csv").rename(columns={"building_zone": "zone", "kwh_consumed": "kwh"})[["timestamp", "zone", "kwh"]]
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / "electric.csv"
        data.to_csv(source, index=False)
        profile = DataProfiler().profile_csv(project["id"], source.read_bytes(), "electric.csv")
        store.save_dataset(project["id"], source, "electric.csv", profile.model_dump(), "Hourly electricity consumption by building zone, in kWh.")
    draft = revision()
    store.save_revision(project["id"], draft)
    service = ProjectService(store)
    run = await service.execute(project["id"], draft, {}, lambda _: None, threading.Event())
    if run.status != "succeeded":
        raise RuntimeError(run.error)
    store.message(project["id"], "assistant", "Reference project validated without an LLM. Review the cleanup rules, try controls, and accept when ready.")
    return store.view(project["id"])


def main() -> None:
    from backend.routes.project_routes import store
    view = asyncio.run(create_demo(store))
    print(f"Validated demo project: {view['project']['id']}")


if __name__ == "__main__":
    main()
