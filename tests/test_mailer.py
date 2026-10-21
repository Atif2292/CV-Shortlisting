import io
import json
import urllib.error

import pytest

from utils import config, mailer


class _Resp(io.BytesIO):
    def __init__(self, body=b"", status=201):
        super().__init__(body)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


@pytest.fixture(autouse=True)
def brevo(monkeypatch):
    monkeypatch.setattr(config, "BREVO_API_KEY", "xkeysib-test")
    monkeypatch.setattr(config, "EMAIL_FROM", "")
    mailer._brevo_sender_cache.clear()
    yield
    mailer._brevo_sender_cache.clear()


def _fake_brevo(monkeypatch, senders, calls):
    def fake_urlopen(req, timeout=15):
        calls.append((req.get_method(), req.full_url, json.loads(req.data) if req.data else None))
        if req.full_url.endswith("/senders"):
            return _Resp(json.dumps({"senders": senders}).encode(), 200)
        return _Resp(b'{"messageId":"x"}', 201)
    monkeypatch.setattr(mailer.urllib.request, "urlopen", fake_urlopen)


def test_sender_is_detected_from_brevo_and_cached(monkeypatch):
    calls = []
    _fake_brevo(monkeypatch, [{"email": "old@acme.co.uk", "active": False},
                              {"email": "owner@acme.co.uk", "active": True}], calls)
    assert mailer.send_login_code("lead@client.co.uk", "123456")
    assert mailer.send_login_code("lead2@client.co.uk", "654321")
    sends = [c for c in calls if c[1].endswith("/smtp/email")]
    assert [c[2]["sender"]["email"] for c in sends] == ["owner@acme.co.uk"] * 2
    assert sum(1 for c in calls if c[1].endswith("/senders")) == 1      # looked up once


def test_email_from_overrides_detection(monkeypatch):
    calls = []
    monkeypatch.setattr(config, "EMAIL_FROM", "no-reply@acme.co.uk")
    _fake_brevo(monkeypatch, [{"email": "owner@acme.co.uk", "active": True}], calls)
    assert mailer.send_login_code("lead@client.co.uk", "123456")
    assert not any(c[1].endswith("/senders") for c in calls)
    assert calls[-1][2]["sender"]["email"] == "no-reply@acme.co.uk"


def test_no_verified_sender_means_no_send(monkeypatch):
    calls = []
    _fake_brevo(monkeypatch, [{"email": "pending@acme.co.uk", "active": False}], calls)
    assert not mailer.send_login_code("lead@client.co.uk", "123456")
    assert not any(c[1].endswith("/smtp/email") for c in calls)


def test_brevo_errors_are_handled(monkeypatch):
    def boom(req, timeout=15):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b"{}"))
    monkeypatch.setattr(mailer.urllib.request, "urlopen", boom)
    assert not mailer.send_login_code("lead@client.co.uk", "123456")
