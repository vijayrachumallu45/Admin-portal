from tests.conftest import login


def test_dashboard_includes_system_status(client):
    login(client)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"System status" in response.data
    assert b"Healthy" in response.data or b"Operational" in response.data
