"""Integration tests for FastAPI endpoints."""

from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app import app


@pytest.mark.asyncio
async def test_full_session_lifecycle_and_upload() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["app"] == "WPS-AI"
        assert data["status"] == "healthy"

        # 2. Create session
        create_resp = await client.post("/api/sessions", json={"title": "Integration Test Session"})
        assert create_resp.status_code == 201
        session_data = create_resp.json()
        session_id = session_data["session_id"]
        assert session_id

        # 3. Upload dataset
        csv_path = Path(__file__).resolve().parent.parent / "sample_data" / "electric_usage.csv"
        desc_path = Path(__file__).resolve().parent.parent / "sample_data" / "electric_usage_desc.txt"

        with open(csv_path, "rb") as f_csv, open(desc_path, "rb") as f_desc:
            files = {
                "csv_file": ("electric_usage.csv", f_csv, "text/csv"),
                "desc_file": ("electric_usage_desc.txt", f_desc, "text/plain"),
            }
            upload_resp = await client.post(f"/api/sessions/{session_id}/upload", files=files)

        assert upload_resp.status_code == 200
        upload_data = upload_resp.json()
        assert upload_data["metadata"]["row_count"] == 360
        assert upload_data["metadata"]["column_count"] == 7
        assert upload_data["profile"] is not None
        assert len(upload_data["profile"]["columns"]) == 7

        # 4. Get session detail
        detail_resp = await client.get(f"/api/sessions/{session_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["metadata"]["session_id"] == session_id
        assert detail["profile"]["dataset_name"] == "electric_usage.csv"

        # 5. Test CSV export route
        export_resp = await client.post(
            f"/api/sessions/{session_id}/export-csv",
            json={
                "columns": ["zone", "mean_kwh"],
                "rows": [{"zone": "Zone-A", "mean_kwh": 42.5}, {"zone": "Zone-B", "mean_kwh": 78.1}],
                "filename": "summary.csv"
            }
        )
        assert export_resp.status_code == 200
        assert "Zone-A,42.5" in export_resp.text

        # 6. Delete session
        del_resp = await client.delete(f"/api/sessions/{session_id}")
        assert del_resp.status_code == 204
