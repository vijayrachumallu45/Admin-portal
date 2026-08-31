def test_healthz_reports_dependency_checks(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["checks"] == {"database": "ok", "catalog": "ok"}
    assert payload["catalog_domains"] > 0