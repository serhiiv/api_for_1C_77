from functools import lru_cache
from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "api_for_1C_77"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    api_key: str = ""
    api_key_header_name: str = "X-API-Key"

    rabbitmq_default_user: str = "guest"
    rabbitmq_default_pass: str = "guest"
    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = 5672
    rabbitmq_queue: str = "events"
    rabbitmq_result_queue_prefix: str = "results"
    rabbitmq_result_ttl_ms: int = 3600000
    rabbitmq_result_queue_expires_ms: int = 86400000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    @property
    def rabbitmq_url(self) -> str:
        user = quote(self.rabbitmq_default_user, safe="")
        password = quote(self.rabbitmq_default_pass, safe="")
        return (
            f"amqp://{user}:{password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}/"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
