import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file from project root if it exists
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)

def get_anthropic_api_key() -> str | None:
    """
    Return the Anthropic API key from environment variables.
    
    Priority:
    1. ANTHROPIC_API_KEY env var (set by CLI arg or system)
    2. .env file
    
    Returns:
        API key string or None if not found
    """
    return os.getenv("ANTHROPIC_API_KEY")
