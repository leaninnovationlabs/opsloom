import pytest
from backend.util.auth_utils import PasswordService


@pytest.fixture

def service():
    return PasswordService()


def test_hash_and_verify(service: PasswordService):
    password = "secret"
    hashed = service.hash_password(password)
    assert hashed != password
    assert service.verify_password(hashed, password) is True


def test_verify_invalid(service: PasswordService):
    hashed = service.hash_password("secret")
    assert service.verify_password(hashed, "wrong") is False


def test_validate_password_requirements(service: PasswordService):
    ok, msg = service.validate_password_requirements("abc")
    assert ok is False
    assert "at least" in msg
    ok, msg = service.validate_password_requirements("valid")
    assert ok is True
    assert msg == ""
