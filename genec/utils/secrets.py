import os
from pathlib import Path

from dotenv import load_dotenv

_dotenv_loaded = False


def _ensure_dotenv_loaded() -> None:
    """Load .env file from project root or cwd if not already loaded."""
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True

    # Try project root (works in dev mode)
    project_root = Path(__file__).parent.parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
        return

    # Try current working directory (works when installed as package)
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        load_dotenv(cwd_env, override=True)


def get_anthropic_api_key() -> str | None:
    """
    Return the Anthropic API key from environment variables.

    Priority:
    1. ANTHROPIC_API_KEY env var (set by CLI arg or system)
    2. .env file (project root or cwd)

    Returns:
        API key string or None if not found
    """
    _ensure_dotenv_loaded()
    return os.getenv("ANTHROPIC_API_KEY")
