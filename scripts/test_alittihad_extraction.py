import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SUPABASE_URL", "https://supabase.example")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("GEMINI_API_KEYS", "test-key")

import sanaa_press_news_bot as bot  # noqa: E402


ARTICLE_HTML = """
<html><body>
<div class="wrapper-xs" itemtype="http://schema.org/NewsArticle">
  <h3 class="padder heading-font fontztitle text-black">عنوان تجريبي لمقال الاتحاد برس</h3>
  <div class="article-content paragraph-font text-black" itemprop="articleBody">
    <p class="text-md">الاتحاد برس متابعات :
      <p>عنوان تجريبي لمقال الاتحاد برس</p><br/>
      <p>في خطوة مهمة، يوضح هذا النص تفاصيل الخبر الأصلي وما يتصل به من معلومات أساسية ومهمة للقارئ.</p><br/>
      <p>وتستكمل الفقرة الثانية الشرح بمعلومات إضافية مرتبطة مباشرة بموضوع المقال وأطرافه وتفاصيله.</p><br/>
      <p>وتؤكد الفقرة الأخيرة أن هذه التفاصيل تخص الخبر نفسه ولا تتضمن مواد جانبية أخرى.</p>
    </p>
  </div>
</div>
<div class="swiper-container-readAlso">
  <h2 class="readAlsoTitle">أخبار أخرى قد تعجبك</h2>
  <div class="swiper-slide"><h3>عنوان خبر جانبي لا ينتمي إلى المقال</h3></div>
</div>
</body></html>
"""


class AlIttihadExtractionTests(unittest.TestCase):
    def _mock_page(self, mock_fetch):
        response = mock.Mock()
        response.content = ARTICLE_HTML.encode("utf-8")
        response.raise_for_status.return_value = None
        mock_fetch.return_value = response

    @mock.patch.object(bot, "fetch_with_bypass")
    def test_alittihad_uses_generic_extraction_path(self, mock_fetch):
        self._mock_page(mock_fetch)

        result = bot.extract_article("https://alittihadpress.com/news41526.html")

        self.assertIsNotNone(result)
        self.assertIsNone(result["title"])
        self.assertIn("تفاصيل الخبر الأصلي", result["body"])
        # الاتحاد برس لا يملك مساراً خاصاً؛ يمر عبر الاستخراج العام نفسه،
        # لذلك لا تُطبّق عليه تصفية خاصة للكتل الجانبية أو الفقرات المتداخلة.
        self.assertIn("عنوان خبر جانبي", result["body"])
        self.assertGreaterEqual(len(result["body"]), bot.MIN_ACCEPTABLE_LOCAL_LEN)

    @mock.patch.object(bot, "fetch_with_bypass")
    def test_other_domains_keep_their_existing_extraction_behavior(self, mock_fetch):
        self._mock_page(mock_fetch)

        result = bot.extract_article("https://example.com/news")

        self.assertIsNotNone(result)
        self.assertIsNone(result["title"])
        self.assertIn("عنوان خبر جانبي", result["body"])


if __name__ == "__main__":
    unittest.main()
