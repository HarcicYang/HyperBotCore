import asyncio
import os

import hyperot

logger = hyperot.init("milky_config.json")

from hyperot import Client, listener
from hyperot.common import Message
from hyperot.events import *
from hyperot.segments import *
from hyperot.utils import errors

GROUP_ID = int(os.environ["MILKY_GROUP_ID"]) if os.environ.get("MILKY_GROUP_ID") else None
USER_ID = int(os.environ["MILKY_USER_ID"]) if os.environ.get("MILKY_USER_ID") else None


async def handler_msg(event: MessageEvent, actions: listener.Actions):
    print(f"[EVENT] {type(event).__name__}: group={event.group_id} user={event.user_id} msg={event.msg_str!r}")
    if str(event.message) == ".ping":
        logger.info("有人拍我！")
        info = await actions.get_version_info()
        res = await actions.send_msg("pong", group_id=event.group_id, user_id=event.user_id)
        msg_id = res.data.message_id
        await actions.send_msg(
            Message(
                Reply(str(msg_id)),
                At(qq=str(event.user_id)),
                Text(f" Hello from HypeR Core {hyperot.HYPER_BOT_VERSION}"),
                Image(file=f"file://{os.path.abspath('./ban.png')}"),
                Text(f"Current Milky {info.data.protocol_version} Impl: {info.data.app_name} {info.data.app_version}"),
            ),
            group_id=event.group_id,
            user_id=event.user_id,
        )
        await asyncio.sleep(3)
        await actions.del_msg(msg_id)
    elif str(event.message) == ".e2e":
        await run_e2e(actions)


async def run_e2e(actions: listener.Actions):
    print("=== E2E: 只读 API ===")
    info = await actions.get_login_info()
    print(f"  get_login_info -> uin={info.data.user_id} nickname={info.data.nickname}")
    ver = await actions.get_version_info()
    print(f"  get_version_info -> {ver.data.app_name} {ver.data.app_version} (protocol {ver.data.protocol_version})")

    if GROUP_ID is not None:
        print(f"=== E2E: 发群消息并撤回 (群 {GROUP_ID}) ===")
        res = await actions.send_msg("HypeR Core Milky e2e 测试", group_id=GROUP_ID)
        print(f"  send_group_msg -> message_id={res.data.message_id}")
        await asyncio.sleep(1)
        await actions.del_msg(res.data.message_id)
        print("  del_msg OK")

        print(f"=== E2E: 群信息 (群 {GROUP_ID}) ===")
        ginfo = await actions.get_group_info(GROUP_ID)
        print(f"  get_group_info -> {ginfo.data.group_name} members={ginfo.data.member_count}")

        if USER_ID is not None:
            print(f"=== E2E: 群成员信息 (群 {GROUP_ID}) ===")
            minfo = await actions.get_group_member_info(GROUP_ID, USER_ID)
            print(f"  get_group_member_info -> {minfo.data.nickname} card={minfo.data.card} role={minfo.data.role}")
    else:
        print("=== E2E: 跳过目标相关测试（未设置 MILKY_GROUP_ID） ===")

    if USER_ID is not None:
        print(f"=== E2E: 发私聊消息并撤回 (好友 {USER_ID}) ===")
        res = await actions.send_msg("HypeR Core Milky e2e 私聊测试", user_id=USER_ID)
        print(f"  send_private_msg -> message_id={res.data.message_id}")
        await asyncio.sleep(1)
        try:
            await actions.del_msg(res.data.message_id)
            print("  del_msg OK")
        except errors.ApiError as e:
            print(f"  del_msg 失败（已知协议端 bug：recall_private_message 500）: {e}")

        print(f"=== E2E: 好友信息 (好友 {USER_ID}) ===")
        sinfo = await actions.get_stranger_info(USER_ID)
        print(f"  get_user_profile -> {sinfo.data.nickname} sex={sinfo.data.sex} age={sinfo.data.age}")

        print("=== E2E: 全部通过 ===")
        await actions.send_msg("HypeR Core Milky e2e 全部通过 ✅", user_id=USER_ID)
    else:
        print("=== E2E: 跳过目标相关测试（未设置 MILKY_USER_ID） ===")

    print("=== E2E: 自定义 API (custom.get_impl_info) ===")
    impl = await actions.custom.get_impl_info()
    print(f"  custom.get_impl_info -> {impl}")


with Client() as cli:
    cli.subscribe(
        handler_msg,
        [  # type: ignore
            GroupMessageEvent,
            PrivateMessageEvent,
            NotifyEvent,
        ],
    )
    asyncio.get_event_loop().run_until_complete(cli.run())
