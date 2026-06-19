import asyncio
import os
import hyperot

logger = hyperot.init()

from hyperot import listener, Client
from hyperot.events import *
from hyperot.common import Message
from hyperot.segments import *


async def handler_msg(event: GroupMessageEvent, actions: listener.Actions):
    if str(event.message) == "ping":
        logger.info("有人拍我！")
        res = await actions.send("pong", group_id=event.group_id)
        msg_id = res.data.message_id
        await actions.send(Message(Text("Hello from HypeR Core"), Image(file=f"file://{os.path.abspath('./ban.png')}")),
                           group_id=event.group_id)
        await asyncio.sleep(3)
        await actions.del_message(msg_id)


with Client() as cli:
    cli.subscribe(handler_msg, GroupMessageEvent)
    asyncio.get_event_loop().run_until_complete(cli.run())
