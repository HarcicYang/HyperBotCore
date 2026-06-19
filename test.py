import asyncio
import os
from hyperot import configurator

from cfgr.manager import Serializers  # Maybe I've forgotten sth when coding for ucfgr? IDK.

try:
    configurator.BotConfig.load_from("config.json", Serializers.JSON, "hyper-bot")
except FileNotFoundError:
    configurator.BotConfig.create_and_write("config.json", Serializers.JSON)
    print("没有找到配置文件，已自动创建，请填写后重启")
    exit(-1)

config = configurator.BotConfig.get("hyper-bot")

if True:
    from hyperot import hyperogger

    logger = hyperogger.Logger.create("hyper-bot", config.log_level)

    from hyperot.adapters import builtins as adp

    adp.load_onebot()

    from hyperot import listener, Client
    from hyperot.events import *
    from hyperot.common import Message
    from hyperot.segments import *


async def handler_msg(event: GroupMessageEvent, actions: listener.Actions):
    if str(event.message) == "ping":
        logger.info("有人拍我！")
        res = await actions.send("pong", group_id=event.group_id)
        msg_id = res.data.message_id
        await actions.send(Message(Text("Hello from HypeR Core"), Image(file=f"file://{os.path.abspath('./ban.png')}")), group_id=event.group_id)
        await asyncio.sleep(3)
        await actions.del_message(msg_id)


with Client() as cli:
    cli.subscribe(handler_msg, GroupMessageEvent)
    asyncio.get_event_loop().run_until_complete(cli.run())
