import pytest


pytestmark = pytest.mark.skip(reason="manual integration smoke test; requires local vector store and external LLM")


def test_comparison():
    pass
