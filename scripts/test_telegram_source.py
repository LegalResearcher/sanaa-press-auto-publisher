import os
import sys
import unittest
from contextlib import ExitStack
from datetime import timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import telegram_source as source  # noqa: E402

CHANNEL_ID = "-1009876543210"


class TelegramSourceItemTests(unittest.TestCase):
    def test_text_post_becomes_raw_news_item(self):
        update = {
            "update_id": 9001,
            "channel_post": {
                "message_id": 42,
                "date": 1790360000,
                "chat": {"id": int(CHANNEL_ID)},
                "text": "عنوان الخبر\n\nتفاصيل الخبر كاملة.",
            },
        }
        item = source._to_news_item(update, CHANNEL_ID)
        self.assertIsNotNone(item)
        self.assertEqual(item["title"], "عنوان الخبر")
        self.assertEqual(item["raw_body"], "عنوان الخبر\n\nتفاصيل الخبر كاملة.")
        self.assertEqual(item["link"], f"https://t.me/c/{CHANNEL_ID[4:]}/42")
        self.assertEqual(item["source_feed"], f"telegram://{CHANNEL_ID}")
        self.assertEqual(item["category"], "أخبار وتقارير")
        self.assertEqual(item["_telegram_update_id"], 9001)
        self.assertEqual(item["pub_date"].tzinfo, timezone.utc)

    def test_photo_caption_uses_largest_photo(self):
        update = {
            "update_id": 9002,
            "channel_post": {
                "message_id": 43,
                "date": 1790360000,
                "chat": {"id": int(CHANNEL_ID)},
                "caption": "عنوان الصورة\nشرح الخبر",
                "photo": [
                    {"file_id": "small", "width": 90, "height": 90},
                    {"file_id": "large", "width": 1280, "height": 960},
                    {"file_id": "wide", "width": 1200, "height": 700},
                ],
            },
        }
        item = source._to_news_item(update, CHANNEL_ID)
        self.assertEqual(item["_telegram_photo_file_id"], "large")
        self.assertEqual(item["raw_body"], "عنوان الصورة\nشرح الخبر")
        self.assertEqual(item["link"], f"https://t.me/c/{CHANNEL_ID[4:]}/43")

    def test_extracts_visible_and_hidden_external_video_links(self):
        visible = source._to_news_item(
            {
                "update_id": 90021,
                "channel_post": {
                    "message_id": 430,
                    "date": 1790360000,
                    "chat": {"id": int(CHANNEL_ID)},
                    "text": "عنوان الفيديو\nhttps://x.com/news/status/12345",
                },
            },
            CHANNEL_ID,
        )
        hidden = source._to_news_item(
            {
                "update_id": 90022,
                "channel_post": {
                    "message_id": 431,
                    "date": 1790360000,
                    "chat": {"id": int(CHANNEL_ID)},
                    "text": "عنوان الفيديو مشاهدة هنا",
                    "entities": [{"type": "text_link", "url": "https://youtu.be/abc123"}],
                },
            },
            CHANNEL_ID,
        )
        self.assertEqual(visible["_telegram_video_url"], "https://x.com/news/status/12345")
        self.assertEqual(hidden["_telegram_video_url"], "https://youtu.be/abc123")

    def test_image_document_is_used_as_telegram_photo(self):
        item = source._to_news_item(
            {
                "update_id": 90023,
                "channel_post": {
                    "message_id": 432,
                    "date": 1790360000,
                    "chat": {"id": int(CHANNEL_ID)},
                    "caption": "عنوان الصورة",
                    "document": {"file_id": "image-file", "mime_type": "image/jpeg"},
                },
            },
            CHANNEL_ID,
        )
        self.assertEqual(item["_telegram_photo_file_id"], "image-file")

    def test_edited_channel_post_with_media_is_recognized(self):
        item = source._to_news_item(
            {
                "update_id": 90024,
                "edited_channel_post": {
                    "message_id": 433,
                    "date": 1790360000,
                    "chat": {"id": int(CHANNEL_ID)},
                    "caption": "عنوان معدل https://x.com/news/status/12346",
                    "photo": [{"file_id": "edited-photo", "width": 900, "height": 600}],
                },
            },
            CHANNEL_ID,
        )
        self.assertTrue(item["_telegram_media_edit"])
        self.assertEqual(item["_telegram_photo_file_id"], "edited-photo")
        self.assertEqual(item["_telegram_video_url"], "https://x.com/news/status/12346")
        self.assertEqual(item["link"], f"https://t.me/c/{CHANNEL_ID[4:]}/433")

    def test_photo_reply_uses_original_news_text_and_original_post_link(self):
        update = {
            "update_id": 9005,
            "channel_post": {
                "message_id": 46,
                "date": 1790360100,
                "chat": {"id": int(CHANNEL_ID)},
                "photo": [{"file_id": "reply-photo", "width": 1200, "height": 900}],
                "reply_to_message": {
                    "message_id": 42,
                    "date": 1790360000,
                    "chat": {"id": int(CHANNEL_ID)},
                    "text": "عنوان الخبر الأصلي\nتفاصيل الخبر الأصلي كاملة.",
                },
            },
        }
        item = source._to_news_item(update, CHANNEL_ID)
        self.assertTrue(item["_telegram_photo_reply"])
        self.assertEqual(item["title"], "عنوان الخبر الأصلي")
        self.assertEqual(item["raw_body"], "عنوان الخبر الأصلي\nتفاصيل الخبر الأصلي كاملة.")
        self.assertEqual(item["link"], f"https://t.me/c/{CHANNEL_ID[4:]}/42")
        self.assertEqual(item["_telegram_photo_file_id"], "reply-photo")

    def test_same_batch_reply_photo_is_merged_into_news_item(self):
        original = source._to_news_item(
            {
                "update_id": 9006,
                "channel_post": {
                    "message_id": 47,
                    "date": 1790360000,
                    "chat": {"id": int(CHANNEL_ID)},
                    "text": "عنوان خبر جديد\nمتن الخبر.",
                    "photo": [{"file_id": "original-photo", "width": 600, "height": 450}],
                },
            },
            CHANNEL_ID,
        )
        reply = source._to_news_item(
            {
                "update_id": 9007,
                "channel_post": {
                    "message_id": 48,
                    "date": 1790360100,
                    "chat": {"id": int(CHANNEL_ID)},
                    "photo": [{"file_id": "reply-photo", "width": 1200, "height": 900}],
                    "reply_to_message": {
                        "message_id": 47,
                        "date": 1790360000,
                        "chat": {"id": int(CHANNEL_ID)},
                        "text": "عنوان خبر جديد\nمتن الخبر.",
                    },
                },
            },
            CHANNEL_ID,
        )
        news, late = source.merge_photo_replies_with_news_items([original, reply])
        self.assertEqual(len(news), 1)
        self.assertEqual(late, [])
        self.assertEqual(news[0]["_telegram_photo_file_id"], "reply-photo")
        self.assertEqual(news[0]["_telegram_update_id"], 9007)

    def test_same_batch_reply_video_is_merged_into_news_item(self):
        original = source._to_news_item(
            {
                "update_id": 90071,
                "channel_post": {
                    "message_id": 471,
                    "date": 1790360000,
                    "chat": {"id": int(CHANNEL_ID)},
                    "text": "خبر مع فيديو\nالتفاصيل هنا.",
                },
            },
            CHANNEL_ID,
        )
        reply = source._to_news_item(
            {
                "update_id": 90072,
                "channel_post": {
                    "message_id": 472,
                    "date": 1790360100,
                    "chat": {"id": int(CHANNEL_ID)},
                    "text": "https://x.com/news/status/12347",
                    "reply_to_message": {
                        "message_id": 471,
                        "date": 1790360000,
                        "chat": {"id": int(CHANNEL_ID)},
                        "text": "خبر مع فيديو\nالتفاصيل هنا.",
                    },
                },
            },
            CHANNEL_ID,
        )
        news, late = source.merge_photo_replies_with_news_items([original, reply])
        self.assertEqual(len(news), 1)
        self.assertEqual(news[0]["_telegram_video_url"], "https://x.com/news/status/12347")
        self.assertEqual(news[0]["_telegram_update_id"], 90072)
        self.assertEqual(late, [])

    def test_original_post_media_for_existing_article_routes_to_late_path(self):
        original = source._to_news_item(
            {
                "update_id": 90073,
                "channel_post": {
                    "message_id": 473,
                    "date": 1790360000,
                    "chat": {"id": int(CHANNEL_ID)},
                    "caption": "خبر سبق نشره https://x.com/news/status/12356",
                    "photo": [{"file_id": "original-photo", "width": 1200, "height": 900}],
                },
            },
            CHANNEL_ID,
        )
        news, late = source.merge_photo_replies_with_news_items(
            [original], existing_source_urls={original["link"]}
        )
        self.assertEqual(news, [])
        self.assertEqual(late, [original])
        self.assertEqual(late[0]["_telegram_photo_file_id"], "original-photo")
        self.assertEqual(late[0]["_telegram_video_url"], "https://x.com/news/status/12356")

    def test_already_published_story_routes_same_batch_photo_reply_to_late_path(self):
        original = source._to_news_item(
            {
                "update_id": 9008,
                "channel_post": {
                    "message_id": 49,
                    "date": 1790360000,
                    "chat": {"id": int(CHANNEL_ID)},
                    "text": "عنوان منشور مسبقًا",
                },
            },
            CHANNEL_ID,
        )
        reply = source._to_news_item(
            {
                "update_id": 9009,
                "channel_post": {
                    "message_id": 50,
                    "date": 1790360100,
                    "chat": {"id": int(CHANNEL_ID)},
                    "photo": [{"file_id": "reply-photo", "width": 1200, "height": 900}],
                    "reply_to_message": {
                        "message_id": 49,
                        "date": 1790360000,
                        "chat": {"id": int(CHANNEL_ID)},
                        "text": "عنوان منشور مسبقًا",
                    },
                },
            },
            CHANNEL_ID,
        )
        news, late = source.merge_photo_replies_with_news_items(
            [original, reply],
            existing_source_urls={original["link"]},
        )
        self.assertEqual(len(news), 1)
        self.assertEqual(late, [reply])

    def test_ignores_other_channels(self):
        update = {
            "update_id": 9003,
            "channel_post": {
                "message_id": 44,
                "date": 1790360000,
                "chat": {"id": -1001234567890},
                "text": "خبر من قناة أخرى",
            },
        }
        self.assertIsNone(source._to_news_item(update, CHANNEL_ID))

    def test_ignores_posts_without_text_or_caption(self):
        update = {
            "update_id": 9004,
            "channel_post": {
                "message_id": 45,
                "date": 1790360000,
                "chat": {"id": int(CHANNEL_ID)},
                "photo": [{"file_id": "photo-only", "width": 400, "height": 300}],
            },
        }
        self.assertIsNone(source._to_news_item(update, CHANNEL_ID))


class TelegramPollingTests(unittest.TestCase):
    def test_fetch_uses_source_credentials_and_resumes_after_saved_update(self):
        update = {
            "update_id": 9010,
            "channel_post": {
                "message_id": 50,
                "date": 1790360000,
                "chat": {"id": int(CHANNEL_ID)},
                "text": "عنوان\nمتن خام كامل",
            },
        }
        environment = {
            "TELEGRAM_SOURCE_BOT_TOKEN": "test-source-token",
            "TELEGRAM_SOURCE_CHAT_ID": CHANNEL_ID,
            "SUPABASE_URL": "https://supabase.example",
            "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
        }
        with (
            mock.patch.dict(os.environ, environment),
            mock.patch.object(source, "get_last_update_id", return_value=9009),
            mock.patch.object(source, "_ensure_polling_mode") as ensure_polling,
            mock.patch.object(source, "_verify_source_channel", return_value="test_bot") as verify_channel,
            mock.patch.object(source, "_telegram_api_call", return_value={"result": [update]}) as api_call,
        ):
            items, cursor = source.fetch_telegram_items()

        self.assertEqual(cursor, 9010)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["raw_body"], "عنوان\nمتن خام كامل")
        ensure_polling.assert_called_once_with("test-source-token")
        verify_channel.assert_called_once_with("test-source-token", CHANNEL_ID)
        self.assertEqual(api_call.call_args.args[1], "getUpdates")
        self.assertEqual(api_call.call_args.args[2]["offset"], 9010)
        self.assertIn("edited_channel_post", api_call.call_args.args[2]["allowed_updates"])

    def test_fetch_and_merge_attach_reply_photo_when_both_updates_are_pending(self):
        updates = [
            {
                "update_id": 9011,
                "channel_post": {
                    "message_id": 51,
                    "date": 1790360000,
                    "chat": {"id": int(CHANNEL_ID)},
                    "text": "خبر منشور الآن\nالتفاصيل الكاملة.",
                },
            },
            {
                "update_id": 9012,
                "channel_post": {
                    "message_id": 52,
                    "date": 1790360100,
                    "chat": {"id": int(CHANNEL_ID)},
                    "photo": [{"file_id": "reply-photo", "width": 1200, "height": 900}],
                    "reply_to_message": {
                        "message_id": 51,
                        "date": 1790360000,
                        "chat": {"id": int(CHANNEL_ID)},
                        "text": "خبر منشور الآن\nالتفاصيل الكاملة.",
                    },
                },
            },
        ]
        environment = {
            "TELEGRAM_SOURCE_BOT_TOKEN": "test-source-token",
            "TELEGRAM_SOURCE_CHAT_ID": CHANNEL_ID,
            "SUPABASE_URL": "https://supabase.example",
            "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
        }
        with (
            mock.patch.dict(os.environ, environment),
            mock.patch.object(source, "get_last_update_id", return_value=9010),
            mock.patch.object(source, "_ensure_polling_mode"),
            mock.patch.object(source, "_verify_source_channel", return_value="test_bot"),
            mock.patch.object(source, "_telegram_api_call", return_value={"result": updates}),
        ):
            items, cursor = source.fetch_telegram_items()
        news, late = source.merge_photo_replies_with_news_items(items)
        self.assertEqual(cursor, 9012)
        self.assertEqual(len(news), 1)
        self.assertEqual(news[0]["_telegram_photo_file_id"], "reply-photo")
        self.assertEqual(news[0]["_telegram_update_id"], 9012)
        self.assertEqual(late, [])

    def test_cursor_commit_uses_sanaa_service_role_key(self):
        environment = {
            "TELEGRAM_SOURCE_BOT_TOKEN": "test-source-token",
            "TELEGRAM_SOURCE_CHAT_ID": CHANNEL_ID,
            "SUPABASE_URL": "https://supabase.example/",
            "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
        }
        with (
            mock.patch.dict(os.environ, environment),
            mock.patch.object(source, "save_last_update_id") as save_cursor,
        ):
            source.commit_telegram_cursor(9010)
        save_cursor.assert_called_once_with(
            "https://supabase.example", "test-service-role-key", 9010
        )


class SanaaTelegramPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SUPABASE_URL", "https://supabase.example")
        os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
        import sanaa_press_news_bot as bot
        cls.bot = bot
        import auto_publish_sanaa_press as publisher
        cls.publisher = publisher

    def test_first_telegram_publish_stores_video_url_outside_editorial_fields(self):
        video_url = "https://x.com/news/status/12352"
        item = {
            "title": "عنوان الخبر",
            "link": f"https://t.me/c/{CHANNEL_ID[4:]}/52",
            "pub_date": __import__("datetime").datetime.fromtimestamp(1790360000, tz=timezone.utc),
            "raw_body": f"عنوان الخبر\nتفاصيل الخبر\n{video_url}",
            "source_feed": f"telegram://{CHANNEL_ID}",
            "category": "أخبار وتقارير",
            "_telegram_source": True,
            "_telegram_video_url": video_url,
            "_telegram_update_id": 99001,
        }
        publisher = self.publisher
        patch_names = (
            "check_system_logs_size", "check_and_notify_scheduled_posts", "get_existing_source_urls",
            "load_blocked_links", "get_recent_published_titles", "get_recent_published_titles_from_db",
            "fetch_telegram_items", "merge_photo_replies_with_news_items", "collect_recent_items",
            "remove_duplicate_news", "apply_full_extraction", "remove_content_duplicate_news",
            "rewrite_article", "check_similar_published_title_db", "get_category_id", "get_post_image_url",
            "word_stats", "extract_keywords", "make_slug", "generate_meta_title", "generate_meta_description",
            "sb_insert", "log_published_title", "save_published_title_to_db", "save_blocked_link", "seed_views",
            "build_canonical_url", "send_to_telegram", "log_discovery_ready", "commit_telegram_cursor",
            "NO_IMAGE_CATEGORIES",
        )
        with ExitStack() as stack:
            for name in patch_names:
                stack.enter_context(mock.patch.object(publisher, name))
            publisher.get_existing_source_urls.return_value = set()
            publisher.load_blocked_links.return_value = set()
            publisher.get_recent_published_titles.return_value = []
            publisher.get_recent_published_titles_from_db.return_value = []
            publisher.fetch_telegram_items.return_value = ([item], 99001)
            publisher.merge_photo_replies_with_news_items.return_value = ([item], [])
            publisher.collect_recent_items.return_value = []
            publisher.remove_duplicate_news.side_effect = lambda values, **kwargs: values
            publisher.remove_content_duplicate_news.side_effect = lambda values, **kwargs: values
            publisher.rewrite_article.return_value = {
                "title": "عنوان محرر", "excerpt": "ملخص محرر", "content": "متن محرر كامل."
            }
            publisher.check_similar_published_title_db.return_value = None
            publisher.get_category_id.return_value = "category-uuid"
            publisher.get_post_image_url.return_value = (None, None)
            publisher.word_stats.return_value = (3, 1)
            publisher.extract_keywords.return_value = []
            publisher.make_slug.return_value = "slug"
            publisher.generate_meta_title.return_value = "seo title"
            publisher.generate_meta_description.return_value = "seo description"
            publisher.sb_insert.return_value = "post-uuid"
            publisher.build_canonical_url.return_value = "https://sanaa.example/story"
            publisher.send_to_telegram.return_value = False
            publisher.NO_IMAGE_CATEGORIES = set()
            publisher.run()
            inserted_mock = publisher.sb_insert
            rewrite_mock = publisher.rewrite_article

        record = inserted_mock.call_args.args[0]
        self.assertEqual(record["external_video_url"], video_url)
        self.assertNotIn(video_url, record["title"])
        self.assertNotIn(video_url, record["excerpt"])
        self.assertNotIn(video_url, record["content"])
        self.assertEqual(rewrite_mock.call_args.kwargs["video_url"], video_url)
        self.assertNotIn(video_url, rewrite_mock.call_args.args[1])

    def test_private_telegram_item_skips_webpage_extraction(self):
        item = {"_telegram_source": True, "link": "https://t.me/c/1234567890/42"}
        with mock.patch.object(self.bot, "extract_article") as extract_article:
            self.bot.apply_full_extraction([item])
        extract_article.assert_not_called()

    def test_telegram_photo_bytes_use_existing_image_pipeline(self):
        with (
            mock.patch.object(self.bot, "image_contains_blocked_logo", return_value=False),
            mock.patch.object(self.bot, "apply_headline_design_to_image", return_value=None),
            mock.patch.object(self.bot, "compress_image_to_webp", return_value=b"processed-webp"),
            mock.patch.object(self.bot, "upload_image_to_supabase", return_value="https://images.example/signed" ) as upload,
        ):
            image_url, square_url = self.bot.get_post_image_url(
                None,
                article_url=None,
                headline_text="عنوان تجريبي",
                source_image_bytes=b"telegram-photo-bytes",
            )
        self.assertEqual(image_url, "https://images.example/signed")
        self.assertEqual(square_url, None)
        upload.assert_called_once_with(b"processed-webp", mock.ANY)

    def test_late_photo_reply_updates_existing_published_article(self):
        reply = {
            "link": f"https://t.me/c/{CHANNEL_ID[4:]}/42",
            "_telegram_photo_file_id": "late-reply-photo",
            "_telegram_reply_to_message_id": 42,
        }
        published = {"id": "post-uuid", "title": "عنوان الخبر"}
        with (
            mock.patch.object(self.publisher, "get_published_post_by_source_url", return_value=published),
            mock.patch.object(self.publisher, "download_telegram_photo", return_value=b"photo-bytes"),
            mock.patch.object(self.publisher, "get_post_image_url", return_value=("https://image.example/signed", None)) as process_image,
            mock.patch.object(self.publisher, "update_published_post_cover_image", return_value=True) as update_cover,
        ):
            retry_required = self.publisher._process_late_telegram_photo_replies([reply])

        self.assertFalse(retry_required)
        process_image.assert_called_once_with(
            None,
            headline_text="عنوان الخبر",
            source_image_bytes=b"photo-bytes",
        )
        update_cover.assert_called_once_with("post-uuid", "https://image.example/signed")

    def test_late_video_reply_updates_external_video_url(self):
        reply = {
            "link": f"https://t.me/c/{CHANNEL_ID[4:]}/42",
            "_telegram_video_url": "https://x.com/news/status/12348",
            "_telegram_video_reply": True,
        }
        published = {"id": "post-uuid", "title": "عنوان الخبر"}
        with (
            mock.patch.object(self.publisher, "get_published_post_by_source_url", return_value=published),
            mock.patch.object(self.publisher, "update_published_post_video_url", return_value=True) as update_video,
        ):
            retry_required = self.publisher._process_late_telegram_photo_replies([reply])
        self.assertFalse(retry_required)
        update_video.assert_called_once_with("post-uuid", "https://x.com/news/status/12348")

    def test_duplicate_telegram_video_is_attached_to_matching_published_article(self):
        item = {
            "_duplicate_match_title": "عنوان الخبر المنشور",
            "_telegram_video_url": "https://x.com/news/status/12349",
        }
        published = {"id": "post-uuid", "title": "عنوان الخبر المنشور", "external_video_url": None}
        with (
            mock.patch.object(self.publisher, "get_published_post_by_title", return_value=published),
            mock.patch.object(self.publisher, "update_published_post_video_url", return_value=True) as update_video,
        ):
            retry_required = self.publisher._process_duplicate_telegram_media([item])
        self.assertFalse(retry_required)
        update_video.assert_called_once_with("post-uuid", "https://x.com/news/status/12349")

    def test_video_url_is_removed_from_editorial_fields(self):
        url = "https://x.com/news/status/12350"
        text = f"عنوان الخبر {url}\nتفاصيل الخبر {url}"
        self.assertEqual(
            self.publisher._strip_video_url(text, url),
            "عنوان الخبر تفاصيل الخبر",
        )

    def test_title_dedup_transfers_media_to_kept_same_batch_article(self):
        published_at = __import__("datetime").datetime.fromtimestamp(1790360000, tz=timezone.utc)
        first = {"title": "عنوان الخبر", "pub_date": published_at, "raw_body": "تفاصيل"}
        duplicate = {
            "title": "عنوان الخبر",
            "pub_date": published_at,
            "raw_body": "تفاصيل",
            "_telegram_video_url": "https://x.com/news/status/12353",
            "_telegram_update_id": 99002,
        }
        with mock.patch.object(self.bot, "get_title_embedding", side_effect=[[1.0, 0.0], [1.0, 0.0]]):
            kept = self.bot.remove_duplicate_news([first, duplicate])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["_telegram_video_url"], duplicate["_telegram_video_url"])
        self.assertEqual(kept[0]["_telegram_update_id"], 99002)

    def test_title_dedup_returns_media_and_historical_match_title(self):
        published_at = __import__("datetime").datetime.fromtimestamp(1790360000, tz=timezone.utc)
        duplicate = {
            "title": "عنوان الخبر",
            "pub_date": published_at,
            "raw_body": "تفاصيل",
            "_telegram_video_url": "https://x.com/news/status/12354",
        }
        history = [{"title": "عنوان الخبر المنشور", "pub_date": published_at, "embedding": [1.0, 0.0]}]
        removed_media = []
        with mock.patch.object(self.bot, "get_title_embedding", return_value=[1.0, 0.0]):
            kept = self.bot.remove_duplicate_news([duplicate], history_items=history, duplicates_out=removed_media)
        self.assertEqual(kept, [])
        self.assertEqual(removed_media[0]["_duplicate_match_title"], "عنوان الخبر المنشور")

    def test_content_dedup_returns_telegram_media_for_historical_match(self):
        published_at = __import__("datetime").datetime.fromtimestamp(1790360000, tz=timezone.utc)
        duplicate = {
            "title": "تفاصيل الخبر",
            "raw_body": "وزارة الدفاع أعلنت تفاصيل الحدث.",
            "pub_date": published_at,
            "_telegram_video_url": "https://x.com/news/status/12355",
        }
        history = [{
            "title": "عنوان الخبر المنشور",
            "pub_date": published_at,
            "content_embedding": [1.0, 0.0],
            "entities": list(self.bot._extract_entities("وزارة الدفاع")),
        }]
        removed_media = []
        with mock.patch.object(self.bot, "get_content_embedding", return_value=[1.0, 0.0]):
            kept = self.bot.remove_content_duplicate_news(
                [duplicate], history_items=history, duplicates_out=removed_media
            )
        self.assertEqual(kept, [])
        self.assertEqual(removed_media[0]["_telegram_video_url"], duplicate["_telegram_video_url"])
        self.assertEqual(removed_media[0]["_duplicate_match_title"], "عنوان الخبر المنشور")

    def test_late_photo_reply_update_failure_preserves_retry(self):
        reply = {
            "link": f"https://t.me/c/{CHANNEL_ID[4:]}/42",
            "_telegram_photo_file_id": "late-reply-photo",
            "_telegram_reply_to_message_id": 42,
        }
        published = {"id": "post-uuid", "title": "عنوان الخبر"}
        with (
            mock.patch.object(self.publisher, "get_published_post_by_source_url", return_value=published),
            mock.patch.object(self.publisher, "download_telegram_photo", return_value=b"photo-bytes"),
            mock.patch.object(self.publisher, "get_post_image_url", return_value=("https://image.example/signed", None)),
            mock.patch.object(self.publisher, "update_published_post_cover_image", return_value=False),
        ):
            retry_required = self.publisher._process_late_telegram_photo_replies([reply])
        self.assertTrue(retry_required)

    def test_published_source_lookup_matches_exact_telegram_post(self):
        response = mock.Mock(status_code=200)
        response.json.return_value = [{"id": "post-uuid", "title": "عنوان", "status": "published"}]
        source_url = f"https://t.me/c/{CHANNEL_ID[4:]}/42"
        with mock.patch.object(self.bot.requests, "get", return_value=response) as get:
            post = self.bot.get_published_post_by_source_url(source_url)
        self.assertEqual(post["id"], "post-uuid")
        self.assertEqual(get.call_args.kwargs["params"]["source_url"], f"eq.{source_url}")
        self.assertEqual(get.call_args.kwargs["params"]["status"], "eq.published")

    def test_cover_update_changes_only_cover_and_updated_at(self):
        response = mock.Mock(status_code=200)
        response.json.return_value = [{"id": "post-uuid"}]
        with mock.patch.object(self.bot.requests, "patch", return_value=response) as patch:
            updated = self.bot.update_published_post_cover_image(
                "post-uuid", "https://image.example/signed"
            )
        self.assertTrue(updated)
        payload = patch.call_args.kwargs["json"]
        self.assertEqual(payload["cover_image"], "https://image.example/signed")
        self.assertIn("updated_at", payload)
        self.assertEqual(set(payload), {"cover_image", "updated_at"})

    def test_video_update_changes_only_external_url_and_updated_at(self):
        response = mock.Mock(status_code=200)
        response.json.return_value = [{"id": "post-uuid"}]
        with mock.patch.object(self.bot.requests, "patch", return_value=response) as patch:
            updated = self.bot.update_published_post_video_url(
                "post-uuid", "https://x.com/news/status/12351"
            )
        self.assertTrue(updated)
        payload = patch.call_args.kwargs["json"]
        self.assertEqual(payload["external_video_url"], "https://x.com/news/status/12351")
        self.assertIn("updated_at", payload)
        self.assertEqual(set(payload), {"external_video_url", "updated_at"})


if __name__ == "__main__":
    unittest.main()
