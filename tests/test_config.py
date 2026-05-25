from knps.config import KnpsConfig


def test_config_does_not_require_key() -> None:
    config = KnpsConfig.from_env()
    assert config.timeout == 10.0
    assert config.max_rps == 5.0


def test_config_resolves_numeric_options() -> None:
    config = KnpsConfig.from_env(timeout="3.5", max_rps="2")
    assert config.timeout == 3.5
    assert config.max_rps == 2.0
