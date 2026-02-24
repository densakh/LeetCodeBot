import logging
import os
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv


@dataclass
class Config:
    bot_token: str
    anthropic_api_key: str
    allowed_telegram_id: int
    log_level: str = "INFO"
    db_path: str = "data/bot.db"


def load_config() -> Config:
    load_dotenv()
    return Config(
        bot_token=os.environ["BOT_TOKEN"],
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        allowed_telegram_id=int(os.environ["ALLOWED_TELEGRAM_ID"]),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


def setup_logging(level: str = "INFO") -> None:
    os.makedirs("logs", exist_ok=True)

    handler = RotatingFileHandler(
        "logs/bot.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )

    console = logging.StreamHandler()
    console.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.addHandler(handler)
    root.addHandler(console)


COOKIE_INSTRUCTION_RU = """Как получить куки:

1. Открой <a href="https://leetcode.com">leetcode.com</a> и войди в аккаунт
2. Открой DevTools (F12) → вкладка Application → Cookies → leetcode.com
3. Скопируй значение <code>LEETCODE_SESSION</code>
4. Скопируй значение <code>csrftoken</code>

⚠️ Куки действуют ~2 недели, после чего нужно обновить."""

COOKIE_INSTRUCTION_EN = """How to get cookies:

1. Open <a href="https://leetcode.com">leetcode.com</a> and log in
2. Open DevTools (F12) → Application tab → Cookies → leetcode.com
3. Copy the <code>LEETCODE_SESSION</code> value
4. Copy the <code>csrftoken</code> value

⚠️ Cookies are valid for ~2 weeks, then you need to update them."""
