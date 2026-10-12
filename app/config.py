import os

from dotenv import load_dotenv


class ConfigurationError(RuntimeError):
    pass


def get_required_setting(name: str) -> str:
    load_dotenv()
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ConfigurationError(f"Required setting {name} is missing or empty.")
    return value.strip()
