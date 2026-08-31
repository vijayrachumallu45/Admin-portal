from tests.conftest import login


def test_authenticated_navigation_includes_global_search(client):
    login(client)
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert b'href="/search"' in response.data
    assert b">Global search</a>" in response.data