"""Debug mode: lets the developer jump to any level, protected by a password that lives in the private ".env" file.

The password is NEVER written in the source code. Without a ".env" (for example on GitHub or on a player's
computer) there is simply no DEBUG button.  Set MARIO_ENV_FILE to read a different file (the tests do).
"""
import hmac
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def env_file_path():
    return os.environ.get("MARIO_ENV_FILE") or os.path.join(_PROJECT_ROOT, ".env")


def read_env_file(path):
    """Reads KEY=VALUE lines ('#' starts a comment, quotes around the value are removed). Missing file = {}."""
    values = {}
    try:
        with open(path, encoding="utf-8") as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                    value = value[1:-1]
                values[key.strip()] = value
    except OSError:
        pass
    return values


def debug_password():
    """The password from .env, or None when debug mode is not set up (no file, empty, or still the example value)."""
    password = read_env_file(env_file_path()).get("DEBUG_PASSWORD", "")
    return None if password in ("", "change_me") else password


def password_is_correct(typed):
    password = debug_password()
    if password is None:
        return False  # not set up: nothing can ever be correct
    return hmac.compare_digest(typed.encode("utf-8"), password.encode("utf-8"))
