from conftest import auth

from app.seed import DEV_PASSWORD, dev_email


def login(client, email, password, **kw):
    return client.post("/api/auth/login", json={"email": email, "password": password}, **kw)


def token_from(url):
    return url.rsplit("/invite/", 1)[1]


def test_login_wrong_password_and_case_insensitive_email(client):
    assert login(client, dev_email("dev-gm"), "wrong-password").status_code == 401
    assert login(client, "nobody@sample.test", DEV_PASSWORD).status_code == 401
    r = login(client, dev_email("dev-gm").upper(), DEV_PASSWORD)
    assert r.status_code == 200 and r.json()["me"]["role"] == "gm"


def test_login_throttled_after_repeated_failures(client):
    email = dev_email("dev-estimator")
    for _ in range(8):
        assert login(client, email, "nope-nope").status_code == 401
    r = login(client, email, DEV_PASSWORD)
    assert r.status_code == 429


def test_logout_ends_only_that_device(client):
    a = login(client, dev_email("dev-lead-1"), DEV_PASSWORD).json()["token"]
    b = login(client, dev_email("dev-lead-1"), DEV_PASSWORD).json()["token"]
    assert client.post("/api/auth/logout", headers=auth(a)).status_code == 204
    assert client.get("/api/me", headers=auth(a)).status_code == 401
    assert client.get("/api/me", headers=auth(b)).status_code == 200


def test_add_crew_lead_invite_flow(client):
    r = client.post("/api/team", json={"name": "Dana Cole", "role": "crew_lead", "email": "Dana@Example.com", "hourly_cost": 35},
                    headers=auth("dev-gm"))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["person"]["email"] == "dana@example.com" and body["person"]["has_password"] is False
    tok = token_from(body["invite_url"])

    info = client.get(f"/api/auth/invite/{tok}")
    assert info.status_code == 200 and info.json()["name"] == "Dana Cole" and info.json()["resetting"] is False
    assert client.post(f"/api/auth/invite/{tok}", json={"password": "short"}).status_code == 422
    assert client.post(f"/api/auth/invite/{tok}", json={"password": "dana cole"}).status_code == 422
    done = client.post(f"/api/auth/invite/{tok}", json={"password": "court-blue-42"})
    assert done.status_code == 200 and done.json()["me"]["enters_time"] is True
    # Link is single-use; the new password works
    assert client.get(f"/api/auth/invite/{tok}").status_code == 404
    assert login(client, "dana@example.com", "court-blue-42").status_code == 200


def test_crew_member_needs_no_email_and_cannot_sign_in(client):
    r = client.post("/api/team", json={"name": "Eli Ross", "role": "crew", "hourly_cost": 24}, headers=auth("dev-gm"))
    assert r.status_code == 201 and r.json()["invite_url"] is None and r.json()["person"]["signs_in"] is False
    names = [c["name"] for c in client.get("/api/crew", headers=auth("dev-lead-1")).json()]
    assert "Eli Ross" in names
    # Sign-in roles need an email
    assert client.post("/api/team", json={"name": "No Email", "role": "estimator"}, headers=auth("dev-gm")).status_code == 422


def test_password_reset_signs_out_other_devices(client):
    team = client.get("/api/team", headers=auth("dev-gm")).json()
    marco = next(p for p in team if p["name"] == "Marco Diaz")
    old = auth("dev-lead-1")
    url = client.post(f"/api/team/{marco['id']}/invite", headers=auth("dev-gm")).json()["invite_url"]
    assert client.get(f"/api/auth/invite/{token_from(url)}").json()["resetting"] is True
    client.post(f"/api/auth/invite/{token_from(url)}", json={"password": "new-password-9"})
    assert client.get("/api/me", headers=old).status_code == 401
    assert login(client, dev_email("dev-lead-1"), DEV_PASSWORD).status_code == 401
    # A newer link replaces an older unused one
    u1 = client.post(f"/api/team/{marco['id']}/invite", headers=auth("dev-gm")).json()["invite_url"]
    u2 = client.post(f"/api/team/{marco['id']}/invite", headers=auth("dev-gm")).json()["invite_url"]
    assert client.get(f"/api/auth/invite/{token_from(u1)}").status_code == 404
    assert client.get(f"/api/auth/invite/{token_from(u2)}").status_code == 200


def test_deactivate_and_sign_out_everywhere(client):
    team = client.get("/api/team", headers=auth("dev-gm")).json()
    jordan = next(p for p in team if p["name"] == "Jordan Kemp")
    assert jordan["devices"] >= 1
    client.post(f"/api/team/{jordan['id']}/signout", headers=auth("dev-gm"))
    assert client.get("/api/me", headers=auth("dev-lead-2")).status_code == 401
    new = login(client, dev_email("dev-lead-2"), DEV_PASSWORD).json()["token"]
    r = client.patch(f"/api/team/{jordan['id']}", json={"active": False}, headers=auth("dev-gm"))
    assert r.status_code == 200 and r.json()["person"]["active"] is False
    assert client.get("/api/me", headers=auth(new)).status_code == 401
    assert login(client, dev_email("dev-lead-2"), DEV_PASSWORD).status_code == 401
    assert "Jordan Kemp" not in [c["name"] for c in client.get("/api/crew", headers=auth("dev-lead-1")).json()]


def test_team_rules(client):
    team = client.get("/api/team", headers=auth("dev-gm")).json()
    me = next(p for p in team if p["name"] == "Sam Ortiz")
    assert client.patch(f"/api/team/{me['id']}", json={"active": False}, headers=auth("dev-gm")).status_code == 409
    assert client.patch(f"/api/team/{me['id']}", json={"role": "crew"}, headers=auth("dev-gm")).status_code == 409
    for key in ("dev-owner", "dev-estimator", "dev-lead-1"):
        assert client.get("/api/team", headers=auth(key)).status_code == 403
    # Other company can't see or touch our people
    assert client.patch(f"/api/team/{me['id']}", json={"name": "X"}, headers=auth("dev-other-gm")).status_code == 404
    assert all(p["name"] != "Sam Ortiz" for p in client.get("/api/team", headers=auth("dev-other-gm")).json())
    # Email already in use
    r = client.post("/api/team", json={"name": "Dup", "role": "estimator", "email": dev_email("dev-owner")}, headers=auth("dev-gm"))
    assert r.status_code == 409
    # Team list never includes password hashes
    assert all("password_hash" not in p for p in team)


def test_unknown_api_path_is_404_not_app_shell(client):
    assert client.get("/api/nothing-here", headers=auth("dev-gm")).status_code == 404
