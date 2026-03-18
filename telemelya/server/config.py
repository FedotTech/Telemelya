"""Server configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Mock Server
    mock_server_host: str = "0.0.0.0"
    mock_server_port: int = 8080
    mock_server_url: str = "http://localhost:8080"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "test-media"
    minio_use_ssl: bool = False

    # Auth
    auth_keys: str = ""

    @property
    def auth_keys_set(self) -> set[str]:
        if not self.auth_keys:
            return set()
        return {k.strip() for k in self.auth_keys.split(",") if k.strip()}

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
