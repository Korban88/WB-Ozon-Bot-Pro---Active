import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ── OpenRouter (text + vision AI) ─────────────────────────────────────────────
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_URL: str = "https://openrouter.ai/api/v1/chat/completions"

# ── OpenAI (image generation via gpt-image-1) ─────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_IMAGE_MODEL: str = "gpt-image-1"
OPENAI_IMAGE_URL: str = "https://api.openai.com/v1/images/edits"

# ── Together AI (legacy, not used) ────────────────────────────────────────────
TOGETHER_API_KEY: str = os.getenv("TOGETHER_API_KEY", "")
TOGETHER_MODEL: str = "black-forest-labs/FLUX.1-schnell-Free"
TOGETHER_URL: str = "https://api.together.xyz/v1/images/generations"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOGS_DIR: str = os.path.join(os.path.dirname(__file__), "logs")

# ── Assets ────────────────────────────────────────────────────────────────────
IMAGES_DIR: str = os.path.join(os.path.dirname(__file__), "assets", "images")

# ── Validation ────────────────────────────────────────────────────────────────
def validate():
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not OPENROUTER_API_KEY:
        missing.append("OPENROUTER_API_KEY")
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Copy .env.example to .env and fill in the values."
        )
