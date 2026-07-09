from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # База данных (Railway подставит DATABASE_URL автоматически)
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/archery"

    # OpenAI
    OPENAI_API_KEY: str = ""

    # CORS — адреса фронтенда. Можно указать несколько через запятую,
    # например: "https://archery.news,https://www.archery.news,https://archerynews.ru"
    FRONTEND_ORIGIN: str = "https://archerynews.ru"

    @property
    def frontend_origins(self) -> list[str]:
        return [o.strip() for o in self.FRONTEND_ORIGIN.split(",") if o.strip()]

    # VAPID для push (создадим в Части 4)
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:admin@archerynews.ru"

    # Ключ для защиты ручного запуска агента (POST /api/agent/run)
    # Если оставить пустым — эндпоинт не защищён (не рекомендуется в проде).
    ADMIN_API_KEY: str = ""

settings = Settings()
