import asyncio
import json
import unittest
from types import SimpleNamespace

from core.handle.intentHandler import (
    process_intent_result,
    wait_for_intent_dependencies,
)


class _BoundLogger:
    def bind(self, **_kwargs):
        return self

    def warning(self, *_args, **_kwargs):
        return None

    def debug(self, *_args, **_kwargs):
        return None


class IntentReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def test_waits_for_background_components(self):
        ready = asyncio.Event()
        conn = SimpleNamespace(
            components_ready_event=ready,
            config={"component_init_timeout": 0.2},
        )

        async def release():
            await asyncio.sleep(0.01)
            ready.set()

        asyncio.create_task(release())
        self.assertTrue(await wait_for_intent_dependencies(conn))

    async def test_readiness_timeout_is_reported(self):
        conn = SimpleNamespace(
            components_ready_event=asyncio.Event(),
            config={},
        )
        self.assertFalse(await wait_for_intent_dependencies(conn, timeout=0.01))

    async def test_tool_intent_falls_back_when_handler_is_not_ready(self):
        conn = SimpleNamespace(
            func_handler=None,
            logger=_BoundLogger(),
        )
        intent = json.dumps(
            {
                "function_call": {
                    "name": "get_giddy_weather",
                    "arguments": {"day": "today", "location": ""},
                }
            }
        )
        self.assertFalse(await process_intent_result(conn, intent, "que clima hace"))


if __name__ == "__main__":
    unittest.main()
