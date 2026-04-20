from app.core.config import get_settings


def test_settings_loads() -> None:
    settings = get_settings()
    assert settings.app_env
    assert settings.embedding_dimensions > 0
