import asyncio

from hyperot.hyperogger import Logger
from hyperot.utils import KeyQueue
from hyperot.utils.typextensions import ObjectedJson


def test_logger_can_be_fetched_by_name():
    logger = Logger.create("test_module", "ERROR")

    assert Logger.fetch("test_module") is logger
    assert Logger.fetch("missing_module") is None


def test_objected_json_supports_nested_and_item_access():
    value = ObjectedJson({"a": {"b": 2}})

    assert value.a.b == 2
    value.a = {"c": 3}
    value["d"] = 4
    assert value.a.c == 3
    assert value["d"] == 4
    assert value.missing is None


def test_key_queue_preserves_order_and_unblocks_waiters():
    async def run():
        queue = KeyQueue()
        await queue.put("k", 1)
        await queue.put("k", 2)
        assert await queue.get("k") == 1

        task = asyncio.create_task(queue.get("missing"))
        await asyncio.sleep(0)
        await queue.put("missing", "value")
        assert await task == "value"

    asyncio.run(run())
