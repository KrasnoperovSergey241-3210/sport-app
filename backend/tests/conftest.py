import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _env(settings):
    cache.clear()
    settings.DEV_ECHO_OTP = True
