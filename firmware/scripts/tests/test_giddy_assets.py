import json
import struct
import sys
import unittest
from pathlib import Path


FIRMWARE_DIR = Path(__file__).resolve().parents[2]
ASSET_DIR = FIRMWARE_DIR / "custom_emoji" / "robot-pro_240"
sys.path.insert(0, str(FIRMWARE_DIR / "scripts"))

from build_default_assets import add_signed_char_compatibility_padding

REQUIRED_EMOTIONS = {
    "angry",
    "boot",
    "confident",
    "confused",
    "connecting",
    "cool",
    "crying",
    "curious",
    "delicious",
    "dozing",
    "embarrassed",
    "funny",
    "goodnight",
    "happy",
    "kissy",
    "laughing",
    "listening",
    "loving",
    "music",
    "neutral",
    "relaxed",
    "robot_2",
    "sad",
    "shocked",
    "silly",
    "sleepy",
    "speaking",
    "surprised",
    "thinking",
    "wake",
    "winking",
}


class GiddyAssetTests(unittest.TestCase):
    def test_package_checksum_is_compatible_with_deployed_firmware(self):
        data = bytearray([0x80] * 10 + [0x7F] * 3)
        padding = add_signed_char_compatibility_padding(data)

        unsigned_checksum = sum(data) & 0xFFFF
        signed_checksum = sum(value if value < 0x80 else value - 0x100 for value in data)

        self.assertEqual(246, padding)
        self.assertEqual(unsigned_checksum, signed_checksum & 0xFFFF)

    def test_complete_animated_face_collection(self):
        actual = {path.stem for path in ASSET_DIR.glob("*.gif")}
        self.assertEqual(REQUIRED_EMOTIONS, actual)

        for name in sorted(REQUIRED_EMOTIONS):
            data = (ASSET_DIR / f"{name}.gif").read_bytes()
            self.assertIn(data[:6], (b"GIF87a", b"GIF89a"), name)
            self.assertEqual((240, 240), struct.unpack_from("<HH", data, 6), name)
            self.assertGreaterEqual(data.count(b"\x21\xf9\x04"), 2, name)

    def test_face_collection_stays_within_partition_budget(self):
        total_bytes = sum(path.stat().st_size for path in ASSET_DIR.glob("*.gif"))
        self.assertLess(total_bytes, 2 * 1024 * 1024)

    def test_low_battery_alert_is_a_spoken_opus_message(self):
        audio = (FIRMWARE_DIR / "main" / "assets" / "common" / "low_battery.ogg").read_bytes()
        language = json.loads(
            (FIRMWARE_DIR / "main" / "assets" / "locales" / "es-ES" / "language.json")
            .read_text(encoding="utf-8")
        )

        self.assertTrue(audio.startswith(b"OggS"))
        self.assertIn(b"OpusHead", audio[:256])
        self.assertGreater(len(audio), 10_000)
        self.assertEqual(
            "Urgente, cargame que me apago",
            language["strings"]["BATTERY_NEED_CHARGE"],
        )


if __name__ == "__main__":
    unittest.main()
