from app.core.config import Settings, parse_cors_origins


def test_cors_origins_parsing():
    """Verify parse_cors_origins handles list, JSON string, and comma-separated strings."""
    assert parse_cors_origins(["http://localhost:3000"]) == ["http://localhost:3000"]
    assert parse_cors_origins('["http://localhost:3000", "http://localhost:5173"]') == [
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    assert parse_cors_origins("http://localhost:3000, http://localhost:5173") == [
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    assert parse_cors_origins("") == []
    assert parse_cors_origins(None) == []


def test_settings_defaults():
    """Verify application settings have valid default configurations."""
    settings = Settings()
    assert settings.PROJECT_NAME == "TaskFlow AI"
    assert settings.API_V1_STR == "/api/v1"
    assert settings.VERSION == "0.1.0"
    assert settings.ALGORITHM == "HS256"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0
    assert "localhost" in settings.DATABASE_URL
