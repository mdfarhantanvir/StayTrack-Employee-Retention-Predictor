#!/usr/bin/env python3
"""reddit_scraper_praw.py – Scrape posts & comments into a wide CSV."""
from __future__ import annotations
import argparse, os, sys, time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse, parse_qs
import pandas as pd, praw
from prawcore.exceptions import ResponseException

# ─── Credentials ────────────────────────────────────────────────────────────
CLIENT_ID     = "uxWxC7me_Ltfaufqxoaplw"
CLIENT_SECRET = "1CdOTZ8opl9MsxyBoKCk2bddsaQfPQ"
USER_AGENT    = "python:hipaa_scraper:v1.0 (by u/Sea_Carpenter5513)"
DEFAULT_USERNAME = os.getenv("REDDIT_USERNAME")
DEFAULT_PASSWORD = os.getenv("REDDIT_PASSWORD")

# ─── Helpers ────────────────────────────────────────────────────────────────
def parse_input(src: str) -> Tuple[str, str | None]:
    if src.startswith("http"):
        p = urlparse(src)
        q = parse_qs(p.query).get("q", [None])[0]
        sub = p.path.rstrip("/").split("/")[2]
        return sub, q
    if src.lower().startswith("r/"):
        return src[2:], None
    return src, None

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

# ─── Core scraper ───────────────────────────────────────────────────────────
def scrape(reddit: praw.Reddit, sub: str, days: int, limit: int | None,
           pause: float, query: str | None) -> pd.DataFrame:
    cutoff = utc_now() - timedelta(days=days)
    posts = (reddit.subreddit(sub)
             .search(query=query, sort="new", time_filter="all", limit=None)
             if query else
             reddit.subreddit(sub).new(limit=None))
    rows: List[Dict[str, Any]] = []
    for i, post in enumerate(posts, 1):
        if datetime.fromtimestamp(post.created_utc, timezone.utc) < cutoff:
            break
        if limit and i > limit:
            break
        post.comments.replace_more(limit=None)
        comments = [c.body for c in post.comments.list()]
        row: Dict[str, Any] = {
            "post_id": post.id,
            "title": post.title,
            "post_text": post.selftext,
            "created_utc": datetime.utcfromtimestamp(post.created_utc).isoformat(),
            "num_comments": len(comments),
        }
        for idx, body in enumerate(comments, 1):
            row[f"comment_{idx}"] = body
        rows.append(row)
        time.sleep(pause)
    return pd.DataFrame(rows)

# ─── Reddit instance ────────────────────────────────────────────────────────
def make_reddit(user: str | None, pw: str | None) -> praw.Reddit:
    if user and pw:
        print("→ Authenticated mode")
        return praw.Reddit(client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
                           user_agent=USER_AGENT, username=user, password=pw)
    print("→ Read‑only mode")
    return praw.Reddit(client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
                       user_agent=USER_AGENT)

# ─── Main cli ──────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape posts & comments into a wide CSV.")
    parser.add_argument(
        "-s", "--subreddit",
        default="https://www.reddit.com/r/hipaa/search/?q=privacy&cId=6751449e-137e-4037-b7ce-854a551c0edf&iId=428f2920-f4e2-47c3-aafc-2bc84b634a48",
        help="Sub name, r/sub, or full Reddit search URL (default is the privacy search in r/Health)."
    )
    parser.add_argument("--since", type=int, default=730,            # ← changed to 2 years
                        help="Days back to include (default 730 = covers 1 y‑ago posts)")
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--csv", default=None)
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--query", help="Override keyword search")

    a = parser.parse_args()
    sub, url_q = parse_input(a.subreddit)
    q = a.query or url_q
    out_csv = a.csv or f"{sub}_{(q or 'all').replace(' ', '_')}.csv"

    reddit = make_reddit(a.username, a.password)
    label = f"query '{q}'" if q else "posts"
    print(f"Scraping r/{sub} — {label} since {a.since} days …")

    df = scrape(reddit, sub, a.since, None if a.limit <= 0 else a.limit, a.sleep, q)
    df.to_csv(out_csv, index=False)
    print(f"Saved {len(df)} posts → {out_csv}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("Interrupted by user.")
