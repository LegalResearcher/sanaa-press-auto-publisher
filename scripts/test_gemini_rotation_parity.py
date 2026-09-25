import os
import sys
import unittest
from datetime import datetime
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SUPABASE_URL", "https://supabase.example")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("GEMINI_API_KEYS", "legacy-key-1,legacy-key-2")

import sanaa_press_news_bot as bot  # noqa: E402


class GeminiRotationParityTests(unittest.TestCase):
    def setUp(self):
        self.original = {
            name: getattr(bot, name)
            for name in (
                "KEY_GROUPS",
                "NIGHT_MODE",
                "MODEL_CASCADE",
                "_current_group_idx",
                "_current_key_idx",
                "_model_stage_idx",
            )
        }

    def tearDown(self):
        for name, value in self.original.items():
            setattr(bot, name, value)

    def test_loads_semicolon_separated_groups_and_ignores_empty_entries(self):
        with mock.patch.dict(
            os.environ,
            {
                "GEMINI_API_KEYS": "legacy-a,legacy-b",
                "GEMINI_API_KEY_GROUPS": "group-a1, group-a2;; group-b1,group-b2;",
            },
            clear=False,
        ):
            self.assertEqual(
                bot._load_gemini_key_groups(),
                [["group-a1", "group-a2"], ["group-b1", "group-b2"]],
            )

    def test_falls_back_to_gemini_api_keys_as_single_group(self):
        with mock.patch.object(bot, "GEMINI_API_KEYS", ["legacy-a", "legacy-b"]):
            with mock.patch.dict(os.environ, {"GEMINI_API_KEY_GROUPS": "  "}, clear=False):
                self.assertEqual(bot._load_gemini_key_groups(), [["legacy-a", "legacy-b"]])

    def test_day_and_night_cutoff_uses_yemen_time(self):
        self.assertTrue(bot.is_night_mode(datetime(2026, 9, 26, 13, 59, tzinfo=bot.YEMEN_TZ)))
        self.assertFalse(bot.is_night_mode(datetime(2026, 9, 26, 14, 0, tzinfo=bot.YEMEN_TZ)))

    def test_model_cascades_match_hasad(self):
        self.assertEqual(
            bot.DAY_MODEL_CASCADE,
            [
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.7-flash",
                "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite",
            ],
        )
        self.assertEqual(
            bot.NIGHT_MODEL_CASCADE,
            ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"],
        )

    def test_day_exhausts_each_key_models_then_moves_to_next_key_and_group(self):
        bot.KEY_GROUPS = [["day-a1", "day-a2"], ["day-b1"]]
        bot.NIGHT_MODE = False
        bot.MODEL_CASCADE = ["day-model-1", "day-model-2"]
        bot._current_group_idx = 0
        bot._current_key_idx = 0
        bot._model_stage_idx = 0
        seen = []

        def call(*args, **kwargs):
            seen.append((bot.current_key(), bot.current_model()))
            if len(seen) <= 4:
                raise bot.DailyQuotaExceeded()
            return "rewritten"

        with mock.patch.object(bot, "call_gemini", side_effect=call):
            self.assertEqual(bot.call_with_rotation("prompt"), "rewritten")

        self.assertEqual(
            seen,
            [
                ("day-a1", "day-model-1"),
                ("day-a1", "day-model-2"),
                ("day-a2", "day-model-1"),
                ("day-a2", "day-model-2"),
                ("day-b1", "day-model-1"),
            ],
        )
        self.assertEqual((bot._current_group_idx, bot._current_key_idx, bot._model_stage_idx), (1, 0, 0))

    def test_night_starts_at_last_key_and_moves_backwards_through_keys_and_groups(self):
        bot.KEY_GROUPS = [["night-a1", "night-a2"], ["night-b1", "night-b2"]]
        bot.NIGHT_MODE = True
        bot.MODEL_CASCADE = ["night-model-1", "night-model-2"]
        bot._current_group_idx = 1
        bot._current_key_idx = 1
        bot._model_stage_idx = 0
        seen = []

        def call(*args, **kwargs):
            seen.append((bot.current_key(), bot.current_model()))
            if len(seen) <= 4:
                raise bot.DailyQuotaExceeded()
            return "rewritten"

        with mock.patch.object(bot, "call_gemini", side_effect=call):
            self.assertEqual(bot.call_with_rotation("prompt"), "rewritten")

        self.assertEqual(
            seen,
            [
                ("night-b2", "night-model-1"),
                ("night-b2", "night-model-2"),
                ("night-b1", "night-model-1"),
                ("night-b1", "night-model-2"),
                ("night-a2", "night-model-1"),
            ],
        )
        self.assertEqual((bot._current_group_idx, bot._current_key_idx, bot._model_stage_idx), (0, 1, 0))


if __name__ == "__main__":
    unittest.main()
