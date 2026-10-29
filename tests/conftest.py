import pytest
from asb.security.aead import Sealer


@pytest.fixture
def key():
    return Sealer.new_key()


@pytest.fixture
def db(tmp_path, key):
    from asb.store.db import DB
    d = DB(tmp_path / "t.db", key)
    yield d
    d.close()


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


@pytest.fixture
def clock():
    return FakeClock(1000.0)
