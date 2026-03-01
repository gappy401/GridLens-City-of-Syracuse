from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://atlas_admin:password@localhost:5432/atlas"
    REDIS_URL: str = "redis://localhost:6379/0"
    S3_BUCKET: str = "renewable-atlas-data"
    AWS_REGION: str = "us-east-1"
    API_KEY: str = "changeme"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
