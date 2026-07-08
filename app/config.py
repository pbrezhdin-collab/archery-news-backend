from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # База данных (Railway подставит DATABASE_URL автоматически)
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/archery"

    # OpenAI
    OPENAI_API_KEY: str = ""

    # CORS — адрес фронтенда
    FRONTEND_ORIGIN: str = "https://archerynews.ru"

    # VAPID для push (создадим в Части 4)
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:admin@archerynews.ru"

    # Ключ для защиты ручного запуска агента (POST /api/agent/run)
    # Если оставить пустым — эндпоинт не защищён (не рекомендуется в проде).
    ADMIN_API_KEY: str = ""

settings = Settings()
