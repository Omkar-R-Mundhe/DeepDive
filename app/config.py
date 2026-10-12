import os

from dotenv import load_dotenv


class ConfigurationError(RuntimeError):
    pass


def get_setting(name: str, default: str) -> str:
    load_dotenv()
    value = os.getenv(name, default)
    return value.strip()


def get_required_setting(name: str) -> str:
    value = get_setting(name, "")
    if not value:
        raise ConfigurationError(f"Required setting {name} is missing or empty.")
    return value
