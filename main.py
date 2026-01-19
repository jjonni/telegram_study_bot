import asyncio
import logging

from config.config import Config, load_config
from app.bot import main

config: Config = load_config()

logging.basicConfig(
    level = logging.getLevelName(level=config.log.level),
    format = config.log.format
)

asyncio.run(main(config))
