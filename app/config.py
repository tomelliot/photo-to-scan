from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    paperless_url: str = ""
    paperless_token: str = ""
    work_dir: str = "/tmp/paperless-feeder-sessions"

    model_config = {"env_prefix": ""}


def get_settings() -> Settings:
    return Settings()
