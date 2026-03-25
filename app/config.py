from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    APP_NAME: str = "VirtualTryOn-API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Database
    # Docker icinde 'db' servis adinı, locale 'localhost' kullanın
    DATABASE_URL: str = "postgresql://postgres:postgres@db:5432/vtryon"

    # 3D Donusum API (Phase 3)
    TRIPO3D_API_KEY: str = ""      # .env'e TRIPO3D_API_KEY=xxx seklinde ekleyin

    # AWS S3 (Phase 3 — Dosya Depolama)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "eu-central-1"
    S3_BUCKET_NAME: str = ""
    S3_PRESIGNED_EXPIRY: int = 3600   # presigned URL gecerlilik suresi (saniye)

    @property
    def s3_configured(self) -> bool:
        """S3 icin gerekli tum kimlik bilgileri tanimli mi?"""
        return bool(
            self.AWS_ACCESS_KEY_ID
            and self.AWS_SECRET_ACCESS_KEY
            and self.S3_BUCKET_NAME
        )


settings = Settings()

