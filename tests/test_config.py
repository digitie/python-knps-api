import pytest

from knps.config import KnpsConfig
from knps.exceptions import KnpsAuthError


def test_config_normalizes_key() -> None:
    config = KnpsConfig.from_env(api_key=" abc \n 123 ")
    assert config.api_key == "abc123"


def test_config_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KNPS_SERVICE_KEY", raising=False)
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY", raising=False)
    with pytest.raises(KnpsAuthError):
        KnpsConfig.from_env()


def test_knps_env_precedes_common_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KNPS_SERVICE_KEY", "knps")
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "common")
    assert KnpsConfig.from_env().api_key == "knps"
