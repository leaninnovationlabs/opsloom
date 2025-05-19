import time
from backend.util.token_blacklist import InMemoryTokenBlacklist


def test_blacklist_expires():
    bl = InMemoryTokenBlacklist()
    token = "abc"
    bl.add_to_blacklist(token, time.time() + 1)
    assert bl.is_blacklisted(token)
    time.sleep(1.1)
    assert not bl.is_blacklisted(token)
