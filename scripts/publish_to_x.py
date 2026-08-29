"""Publish one successful Sanaa Press article to X.

The script uses a user-context OAuth 2.0 access token supplied as a GitHub
Secret. It never stores or asks for an X password. Set X_POSTING_ENABLED=true
only after OAuth is configured and the owner has approved live publishing.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN", "")
X_POSTING_ENABLED = os.environ.get("X_POSTING_ENABLED", "false").lower() == "true"
SITE_DOMAIN = "https://sanaa-press.vercel.app"
MAX_ATTEMPTS = 3


def supabase_request(method: str, path: str, body: dict | None = None) -> list[dict]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Supabase credentials are not configured")
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        headers["Prefer"] = "return=representation"
        data = json.dumps(body).encode()
    request = Request(f"{SUPABASE_URL}/rest/v1/{path}", data=data, headers=headers, method=method)
    with urlopen(request, timeout=20) as response:
        if response.status not in (200, 201, 204):
            raise RuntimeError(f"Supabase returned HTTP {response.status}")
        raw = response.read().decode()
        return json.loads(raw) if raw else []


def find_latest_post(created_at: str) -> dict | None:
    params = urlencode({
        "select": "id,title,slug,published_at",
        "published_at": f"gte.{created_at}",
        "order": "published_at.desc",
        "limit": "1",
    })
    rows = supabase_request("GET", f"posts?{params}")
    return rows[0] if rows else None


def article_url(post: dict) -> str:
    published = datetime.fromisoformat(str(post["published_at"]).replace("Z", "+00:00"))
    local = published.astimezone(timezone(timedelta(hours=3)))
    return f"{SITE_DOMAIN}/{local:%Y/%m/%d}/{post['slug']}"


def request_x(text: str) -> tuple[str, str]:
    request = Request(
        "https://api.x.com/2/tweets",
        data=json.dumps({"text": text}).encode(),
        headers={
            "Authorization": f"Bearer {X_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode())
        post_id = str(payload.get("data", {}).get("id", ""))
        if not post_id:
            raise RuntimeError("X returned no post id")
        return post_id, f"https://x.com/i/web/status/{post_id}"


def main() -> int:
    if not X_POSTING_ENABLED:
        print("X_DISABLED: no post was sent")
        return 0
    if not X_ACCESS_TOKEN:
        raise RuntimeError("X_ACCESS_TOKEN is missing")

    created_at = os.environ.get("WORKFLOW_RUN_CREATED_AT") or datetime.now(timezone.utc).isoformat()
    post = find_latest_post(created_at)
    if not post:
        print("X_SKIPPED: no newly published Sanaa Press article found")
        return 0

    source_key = f"sanaa-press:{post['id']}"
    existing = supabase_request("GET", f"x_publications?source_key=eq.sanaa-press%3A{post['id']}&select=id,status,x_post_url&limit=1")
    if existing and existing[0].get("status") == "published":
        print("X_DUPLICATE: article was already published")
        return 0

    title = str(post.get("title", "")).strip()
    url = article_url(post)
    text = f"{title}\n{url}"
    try:
        supabase_request("POST", "x_publications", {"source_key": source_key, "source_run_id": os.environ.get("GITHUB_RUN_ID"), "title": title, "article_url": url, "status": "pending", "attempts": 0})
    except HTTPError as error:
        if error.code != 409:
            raise

    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            x_id, x_url = request_x(text)
            supabase_request("PATCH", f"x_publications?source_key=eq.{source_key}", {"status": "published", "x_post_id": x_id, "x_post_url": x_url, "attempts": attempt, "published_at": datetime.now(timezone.utc).isoformat(), "last_attempt_at": datetime.now(timezone.utc).isoformat()})
            print(f"X_PUBLISHED: {x_url}")
            return 0
        except (HTTPError, URLError, TimeoutError, RuntimeError) as error:
            last_error = str(error)
            if isinstance(error, HTTPError) and error.code in (401, 403):
                break
            if attempt < MAX_ATTEMPTS:
                time.sleep(2 ** (attempt - 1))
    supabase_request("PATCH", f"x_publications?source_key=eq.{source_key}", {"status": "failed", "error_message": last_error[:1000], "attempts": MAX_ATTEMPTS, "last_attempt_at": datetime.now(timezone.utc).isoformat()})
    print(f"X_FAILED: {last_error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
