import time
from datetime import datetime, timedelta

from backend.util.token_blacklist import (
    token_blacklist,
    add_token_to_blacklist,
    check_token_blacklist,
)


def test_token_blacklist_add_and_expire(monkeypatch):
    token_blacklist._blacklist.clear()
    token_id = "testtoken"
    add_token_to_blacklist(token_id, datetime.now() + timedelta(seconds=1))
    assert check_token_blacklist(token_id) is True

    # simulate time after expiry
    monkeypatch.setattr(time, "time", lambda: time.time() + 2)
    assert check_token_blacklist(token_id) is False
