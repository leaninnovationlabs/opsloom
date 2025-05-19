import time
from backend.util.token_blacklist import (
    add_token_to_blacklist,
    check_token_blacklist,
    token_blacklist,
)


def test_token_blacklist_expiry(monkeypatch):
    token_blacklist._blacklist.clear()
    token_id = "token123"
    now = time.time()
    add_token_to_blacklist(token_id, expires_at=None)
    assert check_token_blacklist(token_id)

    future = now + 3601
    monkeypatch.setattr(time, "time", lambda: future)
    assert not check_token_blacklist(token_id)
