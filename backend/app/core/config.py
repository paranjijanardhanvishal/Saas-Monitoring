from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "SaaS Security Monitor - Step 1"
    API_V1_STR: str = "/api"
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "saas_monitor"

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), env_file_encoding="utf-8")

settings = Settings()
