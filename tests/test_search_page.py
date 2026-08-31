from tests.conftest import login


def test_global_search_page_lists_results(client):
    login(client)
    response = client.get("/search?q=tenant")
    assert response.status_code == 200
    assert b"Global search" in response.data
    assert b"Tenant Directory" in response.data or b"results" in response.data.lower()
