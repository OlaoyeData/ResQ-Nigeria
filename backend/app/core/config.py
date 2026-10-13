from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./resq.db"
    jwt_secret: str = "dev-only-change-this-secret"
    ai_provider: str = "mock"
    ai_api_key: str = ""
    ai_model: str = ""
    nipost_provider: str = "mock"
    nipost_api_base_url: str = "https://api.postcode.gov.ng"
    nipost_api_key: str = ""
    nipost_access_token: str = ""
    whatsapp_provider: str = "mock"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "development-verify-token"
    whatsapp_business_account_id: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_api_version: str = ""
    cors_origins: str = "http://localhost:5173"
    confidence_high: float = 0.8
    confidence_medium: float = 0.5
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
