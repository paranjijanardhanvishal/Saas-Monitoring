from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "SaaS Security Monitor"
    API_V1_STR: str = "/api"
    APP_ENV: str = "development"

    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "saas_monitor"

    # Initial administrator bootstrap
    ADMIN_EMAIL: str = "admin@admin.com"
    ADMIN_USER_ID: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    AUTO_SYNC_ADMIN_CREDENTIALS: bool = True

    # Comma separated list of allowed browser origins.
    FRONTEND_URL: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Authentication. JWT_SECRET_KEY must be supplied in production.
    JWT_SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    # Server-to-server SaaS proxy ingestion credential. Never ships to browsers.
    INGESTION_API_KEY: str = ""

    # PII engine selection: auto | presidio | regex
    PII_ENGINE: str = "auto"
    PII_MAX_TEXT_LENGTH: int = 100000

    # Local OCR upload limits. Tesseract and Python OCR packages are optional.
    TESSERACT_CMD: str = ""
    OCR_MAX_FILE_BYTES: int = 10485760
    OCR_MAX_PAGES: int = 10

    # Agent liveness / risk pipeline
    AGENT_HEARTBEAT_STALE_SECONDS: int = 180
    AUTO_RISK_ENABLED: bool = True

    # Email / Password Reset Service (optional)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "security@saas-security-monitor.com"

    # Data retention (days). 0 disables automatic deletion.
    EVENT_RETENTION_DAYS: int = 90
    AUDIT_RETENTION_DAYS: int = 365

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
