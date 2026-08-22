import unittest

from config import manage_api_client


class StandaloneManageApiClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.previous_instance = manage_api_client.ManageApiClient._instance
        manage_api_client.ManageApiClient._instance = None

    async def asyncTearDown(self):
        manage_api_client.ManageApiClient._instance = self.previous_instance

    async def test_history_helpers_are_noops_without_central_management(self):
        summary = await manage_api_client.generate_and_save_chat_summary("session")
        title = await manage_api_client.generate_and_save_chat_title("session")

        self.assertIsNone(summary)
        self.assertIsNone(title)


if __name__ == "__main__":
    unittest.main()
