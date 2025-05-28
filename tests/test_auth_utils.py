import pytest
from backend.util.auth_utils import PasswordService


def test_hash_and_verify_password():
    service = PasswordService()
    plain = "s3cret"
    hashed = service.hash_password(plain)
    assert hashed.startswith("$argon2")
    assert service.verify_password(hashed, plain)
    assert not service.verify_password(hashed, "wrong")


def test_validate_password_requirements():
    service = PasswordService()
    ok, msg = service.validate_password_requirements("abcd")
    assert ok
    ok, msg = service.validate_password_requirements("abc")
    assert not ok
    assert "at least" in msg
