import os
import pytest
from unittest.mock import patch

@pytest.fixture(autouse=True)
def test_env():
    """Ensure we're using test settings."""
    with patch.dict(os.environ, {"ENV_NAME": "test"}):
        yield 