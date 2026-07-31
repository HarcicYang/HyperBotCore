from . import configurator, events

config = configurator.BotConfig.get("hyper-bot")

__all__ = ["Actions", "config", "reg", "run", "stop"]

from .adapters.listener import *

events.init()
