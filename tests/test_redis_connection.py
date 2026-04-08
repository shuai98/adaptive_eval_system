import pytest


pytestmark = pytest.mark.skip(reason="manual integration smoke test; requires a local Redis server")


def test_redis_connection():
    pass
