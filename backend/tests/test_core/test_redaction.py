import pytest

from src.shared.core import redaction


def test_redact_email():
    s = "Contact alice@example.com for access"
    out = redaction.redact_text(s)
    assert "alice@example.com" not in out
    assert "***" in out


def test_redact_secret_keys():
    rec = {
        "password": "hunter2",
        "secret": "s3cr3t",
        "token": "tok_abc",
        "authorization": "Bearer xyz",
        "api_key": "key_123",
        "safe": "value",
    }
    out = redaction.redact_value(rec)
    assert out["password"] == "***"
    assert out["secret"] == "***"
    assert out["token"] == "***"
    assert out["authorization"] == "***"
    assert out["api_key"] == "***"
    assert out["safe"] == "value"


def test_redaction_filter():
    rf = redaction.RedactionFilter()
    import logging
    r = logging.LogRecord('t', 20, '', 0, 'Contact alice@example.com', (), None)
    assert rf.filter(r) is True
    assert 'alice' not in r.msg


def test_redact_dsn():
    dsn = "postgresql://user:pass@host:5432/db"
    out = redaction.redact_dsn(dsn)
    assert ":pass@" not in out
    assert "***" in out
