import pytest


pytestmark = pytest.mark.skip(reason="manual integration smoke test; requires running server and local reranker")


def test_rerank():
    pass
