"""Preview the latest Sanaa Press article for a future X publisher.

This script intentionally never calls X and never publishes content. It only
reads the latest published post from Supabase and prints a sanitized preview.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SITE_DOMAIN = "https://sanaa-press.vercel.app"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def get_latest_post(since: str | None) -> dict | None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    params = {
        "select": "title,slug,published_at",
        "order": "published_at.desc",
        "limit": "1",
    }
    if since:
        params["published_at"] = f"gte.{since}"
    url = f"{SUPABASE_URL}/rest/v1/posts?{urlencode(params)}"
    request = Request(
        url,
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
    )
    with urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"Supabase returned HTTP {response.status}")
        rows = json.loads(response.read().decode("utf-8"))
    return rows[0] if rows else None


def canonical_url(post: dict) -> str:
    published = datetime.fromisoformat(str(post["published_at"]).replace("Z", "+00:00"))
    yemen = timezone(timedelta(hours=3))
    local = published.astimezone(yemen)
    return f"{SITE_DOMAIN}/{local:%Y/%m/%d}/{post['slug']}"


def main() -> int:
    created_at = os.environ.get("WORKFLOW_RUN_CREATED_AT")
    post = get_latest_post(created_at)
    if not post:
        print("X_PREVIEW_EMPTY: no published Sanaa Press post found for this run")
        return 0
    print("X_PREVIEW_ONLY: no post was sent to X")
    print(f"title={post.get('title', '')}")
    print(f"url={canonical_url(post)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
