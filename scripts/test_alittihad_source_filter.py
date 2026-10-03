import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SUPABASE_URL", "https://supabase.example")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("GEMINI_API_KEYS", "test-key")

import auto_publish_sanaa_press as publisher  # noqa: E402


class AlIttihadSourceFilterTests(unittest.TestCase):
    def test_each_phrase_blocks_from_title_or_summary(self):
        for phrase in publisher.ALITTIHAD_BLOCKED_TITLE_SUMMARY_PHRASES:
            for field in ("title", "raw_body"):
                with self.subTest(phrase=phrase, field=field):
                    item = {
                        "source_feed": publisher.RSS_ALITTIHAD_PRESS_URL,
                        "title": "عنوان عادي",
                        "raw_body": "ملخص عادي",
                    }
                    item[field] = f"نص قبل العبارة {phrase} ونص بعدها"
                    self.assertTrue(publisher._is_blocked_auto_topic(item))

    def test_sanaa_mention_bypasses_alittihad_phrase_filter(self):
        for phrase in publisher.ALITTIHAD_BLOCKED_TITLE_SUMMARY_PHRASES:
            for field in ("title", "raw_body"):
                with self.subTest(phrase=phrase, field=field):
                    item = {
                        "source_feed": publisher.RSS_ALITTIHAD_PRESS_URL,
                        "title": "عنوان عادي",
                        "raw_body": "ملخص عادي",
                    }
                    item[field] = f"صنعاء {phrase} بقية الخبر"
                    self.assertFalse(publisher._is_blocked_auto_topic(item))

    def test_phrases_do_not_block_other_feeds(self):
        for phrase in publisher.ALITTIHAD_BLOCKED_TITLE_SUMMARY_PHRASES:
            with self.subTest(phrase=phrase):
                item = {
                    "source_feed": publisher.RSS_YPAGENCY_YEMEN_URL,
                    "title": phrase,
                    "raw_body": "ملخص عادي",
                }
                self.assertFalse(publisher._is_blocked_auto_topic(item))

    def test_unrelated_alittihad_item_remains_unblocked(self):
        item = {
            "source_feed": publisher.RSS_ALITTIHAD_PRESS_URL,
            "title": "خبر محلي عن مشروع خدمي",
            "raw_body": "تفاصيل الخبر لا تتضمن أي عبارة محظورة.",
        }
        self.assertFalse(publisher._is_blocked_auto_topic(item))

    def test_future_alittihad_publish_date_is_clamped_to_now(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        normalized = publisher.normalize_publish_date(
            future, publisher.RSS_ALITTIHAD_PRESS_URL
        )
        self.assertLessEqual(normalized, datetime.now(timezone.utc))

    def test_other_feed_publish_date_is_not_changed(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        self.assertEqual(
            publisher.normalize_publish_date(future, publisher.RSS_YPAGENCY_YEMEN_URL),
            future,
        )

    def test_existing_global_keyword_filter_still_applies(self):
        item = {
            "source_feed": publisher.RSS_ALITTIHAD_PRESS_URL,
            "title": "حالة الطقس اليوم",
            "raw_body": "ملخص النشرة",
        }
        self.assertTrue(publisher._is_blocked_auto_topic(item))


if __name__ == "__main__":
    unittest.main()
