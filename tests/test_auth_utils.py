import pytest
from backend.util.auth_utils import PasswordService


def test_password_roundtrip():
    service = PasswordService()
    hashed = service.hash_password("secret")
    assert service.verify_password(hashed, "secret")
    assert not service.verify_password(hashed, "wrong")


def test_password_requirements():
    service = PasswordService()
    valid, msg = service.validate_password_requirements("abc")
    assert not valid
    assert "at least" in msg
    valid, msg = service.validate_password_requirements("goodpass")
    assert valid
