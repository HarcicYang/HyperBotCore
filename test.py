import asyncio
import os
import hyperot

logger = hyperot.init()

from hyperot import listener, Client
from hyperot.events import *
from hyperot.common import Message
from hyperot.segments import *


async def handler_msg(event: MessageEvent, actions: listener.Actions):
    if str(event.message) == ".ping":
        logger.info("有人拍我！")
        info = await actions.get_version_info()
        res = await actions.send_msg("pong", group_id=event.group_id, user_id=event.user_id)
        msg_id = res.data.message_id
        await actions.send_msg(
            Message(
                Reply(str(msg_id)), At(qq=str(event.user_id)),
                Text(f" Hello from HypeR Core {hyperot.HYPER_BOT_VERSION}"),
                Image(file=f"file://{os.path.abspath('./ban.png')}"),
                Text(f"Current OenBot {info.data.protocol_version} Impl: {info.data.app_name} {info.data.app_version}")
            ),
            group_id=event.group_id, user_id=event.user_id
        )
        await asyncio.sleep(3)
        await actions.del_msg(msg_id)


with Client() as cli:
    cli.subscribe(handler_msg, [  # type: ignore
        GroupMessageEvent,
        PrivateMessageEvent
    ])
    asyncio.get_event_loop().run_until_complete(cli.run())
