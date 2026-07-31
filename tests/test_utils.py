import asyncio

from hyperot.utils import KeyQueue
from hyperot.utils.errors import (
    ArgsInvalidError,
    BotOfflineError,
    ButtonRowFulledError,
    ConfigError,
    ListenerNotRegisteredError,
    NotSupportError,
)
from hyperot.utils.typextensions import ObjectedJson


def test_objected_json_nested_access():
    oj = ObjectedJson({"a": {"b": 2}})
    assert oj.a.b == 2


def test_objected_json_missing_attr():
    oj = ObjectedJson({"a": 1})
    assert oj.missing is None


def test_objected_json_setattr():
    oj = ObjectedJson({})
    oj.a = 3
    assert oj.a == 3


def test_objected_json_item_access():
    oj = ObjectedJson({"a": 1})
    assert oj["a"] == 1
    oj["a"] = 2
    assert oj["a"] == 2


def test_objected_json_list_content():
    oj = ObjectedJson([1, 2, 3])
    assert oj[0] == 1
    assert oj.get is None


def test_objected_json_iter():
    oj = ObjectedJson({"a": 1, "b": 2})
    assert set(iter(oj)) == {"a", "b"}


def test_key_queue_roundtrip():
    async def run():
        q = KeyQueue()
        await q.put("k", 1)
        await q.put("k", 2)
        assert await q.get("k") == 1

    asyncio.run(run())


def test_key_queue_missing_key_blocks():
    async def run():
        q = KeyQueue()

        async def getter():
            return await q.get("missing")

        task = asyncio.ensure_future(getter())
        await asyncio.sleep(0.02)
        await q.put("missing", "v")
        assert await task == "v"

    asyncio.run(run())


def test_error_hierarchy():
    assert issubclass(ButtonRowFulledError, Exception)
    assert issubclass(NotSupportError, NotImplementedError)
    assert issubclass(ListenerNotRegisteredError, Exception)
    assert issubclass(ArgsInvalidError, Exception)
    assert issubclass(ConfigError, Exception)
    assert issubclass(BotOfflineError, Exception)


def test_error_instances():
    for exc_cls in (
        ButtonRowFulledError,
        NotSupportError,
        ListenerNotRegisteredError,
        ArgsInvalidError,
        ConfigError,
        BotOfflineError,
    ):
        exc = exc_cls("msg")
        assert str(exc) == "msg"
