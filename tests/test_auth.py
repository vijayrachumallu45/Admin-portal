from app.config import DEMO_EMAIL, DEMO_PASSWORD


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def test_login_required_redirect(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code in (302, 303)


def test_login_logout_dashboard(client):
    bad = client.post(
        "/login",
        data={"email": DEMO_EMAIL, "password": "wrong-password"},
        follow_redirects=True,
    )
    assert b"do not match" in bad.data or b"Sign in" in bad.data

    ok = client.post(
        "/login",
        data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        follow_redirects=True,
    )
    assert ok.status_code == 200
    assert b"Command center" in ok.data or b"Good shift" in ok.data

    dash = client.get("/dashboard")
    assert dash.status_code == 200

    out = client.post("/logout", follow_redirects=True)
    assert out.status_code == 200
    again = client.get("/dashboard", follow_redirects=False)
    assert again.status_code in (302, 303)
