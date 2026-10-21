import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    database_url: str = os.environ["DATABASE_URL"]
    jwt_secret: str = os.environ["JWT_SECRET"]
    rate_limit_per_minute: int = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))


settings = Settings()
