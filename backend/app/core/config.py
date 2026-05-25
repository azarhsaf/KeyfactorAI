from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Keyfactor AI Assistant"
    app_version: str = "0.1.0"
    database_url: str

    keyfactor_base_url: str
    keyfactor_api_path: str = "/KeyfactorAPI"
    keyfactor_auth_type: str = "basic"
    keyfactor_username: str = ""
    keyfactor_password: str = ""
    keyfactor_domain: str = ""
    keyfactor_verify_tls: bool = False
    keyfactor_timeout: int = 60

    llm_provider: str = "ollama"
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:3b-instruct"
    offline_mode: bool = True
    auto_pull_model: bool = False

    local_admin_username: str = "admin"
    local_admin_password: str = "admin123"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
