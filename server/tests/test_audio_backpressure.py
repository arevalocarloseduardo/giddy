import asyncio
import unittest

from core.utils.audioRateController import AudioRateController


class AudioBackpressureTests(unittest.IsolatedAsyncioTestCase):
    async def test_waits_until_the_audio_queue_has_capacity(self):
        controller = AudioRateController(frame_duration=60, max_buffered_packets=20)
        for index in range(20):
            controller.add_audio(bytes([index]))

        waiter = asyncio.create_task(controller.wait_for_capacity())
        await asyncio.sleep(0.01)
        self.assertFalse(waiter.done())

        controller.queue.popleft()
        controller.queue_capacity_event.set()
        self.assertTrue(await asyncio.wait_for(waiter, timeout=0.2))

    async def test_abort_releases_a_capacity_waiter(self):
        controller = AudioRateController(frame_duration=60, max_buffered_packets=20)
        for index in range(20):
            controller.add_audio(bytes([index]))
        aborted = True

        self.assertFalse(
            await controller.wait_for_capacity(lambda: aborted)
        )


if __name__ == "__main__":
    unittest.main()
