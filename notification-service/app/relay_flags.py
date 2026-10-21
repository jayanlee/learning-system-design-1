import os


def flag_enabled(name: str, default: str = "true") -> bool:
    return os.environ.get(name, default).lower() in ("1", "true", "yes")
