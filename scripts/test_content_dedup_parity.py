import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SUPABASE_URL", "https://supabase.example")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("GEMINI_API_KEYS", "test-gemini-key")

import sanaa_press_news_bot as bot  # noqa: E402


class ContentDedupParityTests(unittest.TestCase):
    def test_hasad_content_dedup_settings_and_entity_allowlist(self):
        self.assertEqual(bot.CONTENT_DUPLICATE_EMBEDDING_THRESHOLD, 0.80)
        self.assertEqual(bot.CONTENT_DUPLICATE_TIME_WINDOW_MINUTES, 180)
        self.assertEqual(bot.CONTENT_EMBEDDING_CHARS, 400)
        self.assertEqual(
            bot.KNOWN_ENTITIES,
            [
                "المجلس السياسي الأعلى",
                "التحالف بقيادة السعودية",
                "الحكومة المعترف بها دولياً",
                "الحاكم العسكري السعودي الشهراني",
                "وزارة الدفاع",
                "وزير الدفاع",
                "القوات المسلحة",
                "العاطفي",
                "عبدالملك الحوثي",
                "بدرالدين الحوثي",
                "قائد الثورة",
                "التحالف السعودي",
                "الحصار",
                "مطار صنعاء",
            ],
        )

    def test_embedding_uses_only_first_400_stripped_characters(self):
        raw_body = "  " + ("أ" * 450) + "  "
        with mock.patch.object(bot, "get_title_embedding", return_value=[0.25]) as embed:
            result = bot.get_content_embedding(raw_body)
        self.assertEqual(result, [0.25])
        embed.assert_called_once_with(raw_body.strip()[:400])

    def test_generic_yemen_mention_alone_does_not_trigger_content_dedup(self):
        now = datetime.now(timezone.utc)
        item = {
            "title": "خبر عن اليمن",
            "raw_body": "تفاصيل خبر عام عن اليمن.",
            "pub_date": now,
        }
        history = [
            {
                "title": "خبر سابق عن اليمن",
                "pub_date": now - timedelta(minutes=5),
                "content_embedding": [1.0, 0.0],
                "entities": ["اليمن"],
            }
        ]
        with mock.patch.object(bot, "get_content_embedding") as embed:
            result = bot.remove_content_duplicate_news([item], history_items=history)
        self.assertEqual(result, [item])
        embed.assert_not_called()
        self.assertEqual(item["_entities"], [])

    def test_matching_specific_entity_and_embedding_excludes_duplicate_and_logs_reason(self):
        now = datetime.now(timezone.utc)
        item = {
            "title": "وزارة الدفاع تعلن مستجدات",
            "raw_body": "وزارة الدفاع أصدرت بياناً حول التطورات.",
            "pub_date": now,
        }
        entities = bot._extract_entities(f"{item['title']} {item['raw_body']}")
        self.assertTrue(entities)
        history = [
            {
                "title": "خبر سابق",
                "pub_date": now - timedelta(minutes=5),
                "content_embedding": [1.0, 0.0],
                "entities": list(entities),
            }
        ]
        with mock.patch.object(bot, "get_content_embedding", return_value=[1.0, 0.0]):
            with self.assertLogs(bot.__name__, level="INFO") as captured:
                result = bot.remove_content_duplicate_news([item], history_items=history)
        self.assertEqual(result, [])
        self.assertTrue(any("100%" in line and "وزارة الدفاع" in line for line in captured.output))

    def test_time_window_prevents_old_match(self):
        now = datetime.now(timezone.utc)
        item = {
            "title": "وزارة الدفاع تعلن مستجدات",
            "raw_body": "وزارة الدفاع أصدرت بياناً حول التطورات.",
            "pub_date": now,
        }
        entities = bot._extract_entities(f"{item['title']} {item['raw_body']}")
        history = [
            {
                "title": "خبر سابق",
                "pub_date": now - timedelta(minutes=181),
                "content_embedding": [1.0, 0.0],
                "entities": list(entities),
            }
        ]
        with mock.patch.object(bot, "get_content_embedding", return_value=[1.0, 0.0]):
            result = bot.remove_content_duplicate_news([item], history_items=history)
        self.assertEqual(result, [item])


if __name__ == "__main__":
    unittest.main()
