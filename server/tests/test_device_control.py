import asyncio
import json
import unittest

from core.websocket_server import WebSocketServer


class FakeWebSocket:
    def __init__(self, fail=False):
        self.fail = fail
        self.messages = []

    async def send(self, message):
        if self.fail:
            raise ConnectionError("closed")
        self.messages.append(message)


class DeviceControlTests(unittest.TestCase):
    def make_server(self):
        server = WebSocketServer.__new__(WebSocketServer)
        server.active_connections = {}
        server.active_connections_lock = asyncio.Lock()
        return server

    def test_reboot_reaches_all_connected_devices(self):
        async def scenario():
            server = self.make_server()
            first = FakeWebSocket()
            second = FakeWebSocket()
            server.active_connections = {"device-a": first, "device-b": second}

            result = await server.send_system_command("reboot")

            self.assertEqual(result["delivered"], ["device-a", "device-b"])
            expected = {"type": "system", "command": "reboot"}
            self.assertEqual(json.loads(first.messages[0]), expected)
            self.assertEqual(json.loads(second.messages[0]), expected)

        asyncio.run(scenario())

    def test_reboot_targets_one_device_and_removes_stale_connection(self):
        async def scenario():
            server = self.make_server()
            healthy = FakeWebSocket()
            stale = FakeWebSocket(fail=True)
            server.active_connections = {"healthy": healthy, "stale": stale}

            result = await server.send_system_command("reboot", "STALE")

            self.assertEqual(result["delivered"], [])
            self.assertEqual(result["unavailable"], ["stale"])
            self.assertNotIn("stale", server.active_connections)
            self.assertEqual(healthy.messages, [])

        asyncio.run(scenario())

    def test_rejects_unknown_system_commands(self):
        async def scenario():
            server = self.make_server()
            with self.assertRaises(ValueError):
                await server.send_system_command("factory-reset")

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
