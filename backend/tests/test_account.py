"""Batch 5: your own settings, and the suggestion box."""
import base64

from conftest import auth


def test_profile_prefs_password_and_devices(client):
    me = client.get("/api/me", headers=auth("dev-lead-2")).json()
    assert me["prefs"]["theme"] == "system" and me["email"] == "lead-2@sample.test"
    r = client.patch("/api/me", json={"phone": "(555) 010-1234", "prefs": {"theme": "dark", "text": "large", "start": "field"}},
                     headers=auth("dev-lead-2")).json()
    assert r["phone"] == "(555) 010-1234" and r["prefs"] == {"theme": "dark", "text": "large", "start": "field"}
    assert client.patch("/api/me", json={"prefs": {"theme": "purple"}}, headers=auth("dev-lead-2")).status_code == 422
    assert client.patch("/api/me", json={"prefs": {"start": "nowhere"}}, headers=auth("dev-lead-2")).status_code == 422
    devices = client.get("/api/me/devices", headers=auth("dev-lead-2")).json()
    assert any(d["this_one"] for d in devices)
    # a wrong current password is refused; a right one changes it
    assert client.post("/api/me/password", json={"current": "nope", "new": "a-new-password"}, headers=auth("dev-lead-2")).status_code == 403
    assert client.post("/api/me/password", json={"current": "courtfield-dev", "new": "short"}, headers=auth("dev-lead-2")).status_code == 422
    r = client.post("/api/me/password", json={"current": "courtfield-dev", "new": "a-new-password"}, headers=auth("dev-lead-2"))
    assert r.status_code == 200
    assert client.get("/api/me", headers=auth("dev-lead-2")).status_code == 200  # this device stays signed in
    ok = client.post("/api/auth/login", json={"email": "lead-2@sample.test", "password": "a-new-password"})
    assert ok.status_code == 200
    client.post("/api/me/password", json={"current": "a-new-password", "new": "courtfield-dev"}, headers=auth("dev-lead-2"))


def test_suggestion_box_with_a_screenshot(client, monkeypatch):
    from app import mailer
    sent = []
    monkeypatch.setenv("FEEDBACK_TO", "owner-of-the-app@example.test")
    monkeypatch.setattr(mailer, "configured", lambda: True)
    monkeypatch.setattr(mailer, "send", lambda to, subject, text, attachments=(), reply_to=None: sent.append((to, subject, text, attachments)))
    f = client.post("/api/feedback", json={"kind": "problem", "text": "The clock out button hides behind the keyboard", "page": "Field"},
                    headers=auth("dev-lead-1")).json()
    png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 300).decode()
    assert client.post("/api/photos", json={"kind": "feedback", "subject_id": f["id"], "name": "shot.png", "data": png, "thumb": png},
                       headers=auth("dev-lead-1")).status_code == 201
    # someone else can't add to it or see it
    assert client.post("/api/photos", json={"kind": "feedback", "subject_id": f["id"], "name": "x.png", "data": png, "thumb": png},
                       headers=auth("dev-lead-2")).status_code == 404
    r = client.post(f"/api/feedback/{f['id']}/send", headers=auth("dev-lead-1")).json()
    assert r["sent"]
    assert len(sent) == 1 and sent[0][0] == ["owner-of-the-app@example.test"] and "problem" in sent[0][1] and "Problem from Marco Diaz" in sent[0][2]
    assert sent[0][3][0][0] == "shot.png" and sent[0][3][0][1] == "image/png"
    mine = client.get("/api/feedback", headers=auth("dev-lead-1")).json()["items"]
    assert mine[0]["emailed"] and mine[0]["screenshots"] == 1
    assert client.get("/api/feedback", headers=auth("dev-lead-2")).json()["items"] == []
    gm = client.get("/api/feedback", headers=auth("dev-gm")).json()["items"]
    assert gm[0]["by"] == "Marco Diaz"
    assert client.patch(f"/api/feedback/{f['id']}", json={"status": "done", "reply": "Fixed in the next update"}, headers=auth("dev-lead-1")).status_code == 403
    assert client.patch(f"/api/feedback/{f['id']}", json={"status": "done", "reply": "Fixed in the next update"}, headers=auth("dev-gm")).json()["status"] == "done"


def test_suggestion_saved_when_email_isnt_set_up(client, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    f = client.post("/api/feedback", json={"kind": "idea", "text": "Dark mode please"}, headers=auth("dev-estimator")).json()
    client.post(f"/api/feedback/{f['id']}/send", headers=auth("dev-estimator"))
    item = client.get("/api/feedback", headers=auth("dev-estimator")).json()["items"][0]
    assert not item["emailed"] and "isn't set up" in item["email_error"]


def test_mailer_builds_the_email_with_attachments(monkeypatch):
    """The real send(), against a stand-in mail server: login, TLS, the message."""
    import smtplib
    from app import mailer
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_USER", "sender@example.test")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.delenv("SMTP_PORT", raising=False)
    monkeypatch.delenv("MAIL_FROM", raising=False)
    seen = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            seen["server"] = (host, port)
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def starttls(self, context=None):
            seen["tls"] = True
        def login(self, user, pw):
            seen["login"] = (user, pw)
        def send_message(self, msg):
            seen["msg"] = msg

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 100
    mailer.send(["owner@example.test"], "Courtfield idea: bigger dates", "Text here",
                [("screenshot-1.jpg", "image/jpeg", jpeg)], reply_to="gm@example.test")
    msg = seen["msg"]
    assert seen["server"] == ("smtp.example.test", 587) and seen["tls"] and seen["login"] == ("sender@example.test", "app-password")
    assert msg["From"] == "sender@example.test" and msg["To"] == "owner@example.test" and msg["Reply-To"] == "gm@example.test"
    att = [p for p in msg.iter_attachments()]
    assert len(att) == 1 and att[0].get_filename() == "screenshot-1.jpg" and att[0].get_content() == jpeg
