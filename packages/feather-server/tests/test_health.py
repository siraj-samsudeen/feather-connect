"""What a monitor is told at /healthz."""

from fastapi.testclient import TestClient

from feather_server.app import create_app

# Nothing listens here: /healthz must answer without the database.
NO_DATABASE = "postgresql://nobody:secret@127.0.0.1:9/nowhere"


def test_healthz_says_the_process_is_alive():
    client = TestClient(create_app(NO_DATABASE))

    response = client.get("/healthz")

    assert (response.status_code, response.json()) == (200, {"status": "alive"})
