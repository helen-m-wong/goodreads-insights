from fastapi.testclient import TestClient
from pathlib import Path
from backend.main import app

client = TestClient(app)

def test_get_total_read():
    csv_path = Path(__file__).parent / "example_20_rows.csv"
    with open(csv_path, "rb") as f:
        response = client.post(
            "/upload-csv",
            files={"file": ("example_20_rows.csv", f, "text/csv")}
        )
    assert response.status_code == 200
    json_data = response.json()
    print(json_data)