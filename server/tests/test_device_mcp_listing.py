import json
import unittest
from types import SimpleNamespace

from core.providers.tools.device_mcp.mcp_handler import (
    send_mcp_tools_list_continue_request,
    send_mcp_tools_list_request,
)


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send(self, message):
        self.messages.append(json.loads(message))


class DeviceMCPListingTests(unittest.IsolatedAsyncioTestCase):
    async def test_requests_privileged_device_tools(self):
        socket = FakeWebSocket()
        conn = SimpleNamespace(features={"mcp": True}, websocket=socket)

        await send_mcp_tools_list_request(conn)

        payload = socket.messages[0]["payload"]
        self.assertEqual(payload["method"], "tools/list")
        self.assertEqual(payload["params"], {"withUserTools": True})

    async def test_keeps_privileged_tools_enabled_across_pages(self):
        socket = FakeWebSocket()
        conn = SimpleNamespace(features={"mcp": True}, websocket=socket)

        await send_mcp_tools_list_continue_request(conn, "self.reboot")

        payload = socket.messages[0]["payload"]
        self.assertEqual(
            payload["params"],
            {"cursor": "self.reboot", "withUserTools": True},
        )


if __name__ == "__main__":
    unittest.main()
