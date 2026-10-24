"""Follow-the-player data for the tracker pack: the client publishes the
field the party stands on (or -1 on the world map) so the pack can open that
town's floor-plan tab."""

import asyncio
import unittest
from unittest import mock

from .. import client, memory


class TestFieldToken(unittest.TestCase):
    def test_field_module_publishes_the_field_id(self):
        self.assertEqual(client.field_token(memory.MODULE_FIELD, 106), 106)

    def test_world_map_publishes_minus_one(self):
        self.assertEqual(client.field_token(memory.MODULE_WORLDMAP, 106), -1)

    def test_other_modules_keep_the_last_value(self):
        for module in (memory.MODULE_BATTLE, memory.MODULE_MENU, memory.MODULE_TITLE):
            self.assertIsNone(client.field_token(module, 106), module)


class _Ctx:
    def __init__(self, module, field):
        self.team, self.slot = 0, 3
        self.sent_field = None
        self.sent = []
        self.ff8 = mock.Mock()
        self.ff8.read_u16.return_value = module
        self.ff8.field_id.return_value = field

    async def send_msgs(self, msgs):
        self.sent.extend(msgs)


class TestPublishField(unittest.TestCase):
    def test_publishes_once_per_change(self):
        ctx = _Ctx(memory.MODULE_FIELD, 106)
        asyncio.run(client.publish_field(ctx))
        asyncio.run(client.publish_field(ctx))
        self.assertEqual(len(ctx.sent), 1)
        msg = ctx.sent[0]
        self.assertEqual(msg["key"], "ff8_field_0_3")
        self.assertEqual(msg["operations"], [{"operation": "replace", "value": 106}])
        ctx.ff8.read_u16.return_value = memory.MODULE_WORLDMAP
        asyncio.run(client.publish_field(ctx))
        self.assertEqual(ctx.sent[-1]["operations"][0]["value"], -1)

    def test_battle_does_not_publish(self):
        ctx = _Ctx(memory.MODULE_BATTLE, 106)
        asyncio.run(client.publish_field(ctx))
        self.assertEqual(ctx.sent, [])


if __name__ == "__main__":
    unittest.main()
