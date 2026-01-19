import logging
from environs import Env
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class BotSettings(BaseModel):
    token: str
    super_admin_ids: list[int]

class DataBaseSettings(BaseModel):
    name: str
    host: str
    port: int
    user: str
    password: str

class LoggingSetting(BaseModel):
    level: str
    format: str

class Config(BaseModel):
    bot: BotSettings
    db: DataBaseSettings
    log: LoggingSetting

def load_config(path: str | None = None) -> Config:
    env = Env()
    env.read_env(path)

    token: str = env("BOT_TOKEN")

    if not token:
        raise ValueError("BOT TOKEN must not be empty")

    raw_ids = env.list("SUPER_ADMIN_IDS", default=[])

    try:
        super_admin_ids = [int(x) for x in raw_ids]
    except ValueError as err:
        raise ValueError(f"SUPER_ADMIN_IDS must be the list of integers, got {raw_ids} insted") from err

    bot = BotSettings(
        token = token,
        super_admin_ids = super_admin_ids
    )

    db = DataBaseSettings(
        name = env("POSTGRES_DB"),
        host = env("POSTGRES_HOST"),
        port = env.int("POSTGRES_PORT"),
        user = env("POSTGRES_USER"),
        password = env("POSTGRES_PASSWORD")
    )

    log = LoggingSetting(
        level = env("LOG_LEVEL"),
        format = env("LOG_FORMAT")
    )

    logger.info("Configuration loaded successfully")

    return Config(
        bot = bot,
        db = db,
        log = log
    )