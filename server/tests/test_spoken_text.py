import unittest

from core.providers.tts.base import sanitize_spoken_text


class SpokenTextTests(unittest.TestCase):
    def test_removes_synthetic_laughter_before_speech(self):
        self.assertEqual(
            sanitize_spoken_text("Jaja, no tengo acceso directo."),
            "no tengo acceso directo.",
        )
        self.assertEqual(
            sanitize_spoken_text("Jejeje. Pongo la cancion."),
            "Pongo la cancion.",
        )
        self.assertEqual(
            sanitize_spoken_text("Si, jaja, pongo la cancion."),
            "Si, pongo la cancion.",
        )

    def test_keeps_normal_text_unchanged(self):
        self.assertEqual(sanitize_spoken_text("Pongo la cancion."), "Pongo la cancion.")

    def test_removes_unsolicited_entertainment_offers(self):
        self.assertEqual(
            sanitize_spoken_text(
                "Si queres, te puedo contar una anecdota graciosa."
            ),
            "",
        )
        self.assertEqual(
            sanitize_spoken_text("Te gustaria escuchar una historia sobre eso?"),
            "",
        )
        self.assertEqual(sanitize_spoken_text("Te animas?"), "")

    def test_keeps_actual_assistant_help(self):
        self.assertEqual(
            sanitize_spoken_text("Si queres, te puedo ayudar a configurarlo."),
            "Si queres, te puedo ayudar a configurarlo.",
        )

    def test_replaces_chinese_output_with_spanish_recovery(self):
        self.assertEqual(
            sanitize_spoken_text("我在这里哦！"),
            "No te entendi. Decimelo de nuevo.",
        )


if __name__ == "__main__":
    unittest.main()
