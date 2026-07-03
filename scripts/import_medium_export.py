#!/usr/bin/env python3
"""Import a Medium article exported from the browser into /articles/<slug>/.

For posts older than Medium's 10-item RSS window. Export the article
body from a logged-in browser (see git history for the serializer
snippet), then run:

  python3 scripts/import_medium_export.py <export.html> <slug> <title> \
      <YYYY-MM-DD> <desc> <tag> <sys|mind> <medium_url> [--popular]

Cleans Medium UI residue, downloads images locally, writes
index.html + meta.json, and rebuilds feed.xml.
"""
import json
import re
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_medium import (ARTICLES_DIR, build_feed, download_images,
                         render_article_page, TH_MONTHS)


def clean_export(raw: str) -> str:
    # drop byline residue before the first content element (some posts
    # open with a hero <figure> before any paragraph)
    starts = [i for i in (raw.find("<p>"), raw.find("<figure>")) if i >= 0]
    if starts and min(starts) > 0:
        raw = raw[min(starts):]
    # Medium image-zoom hint text inside figures
    raw = raw.replace("Press enter or click to view image in full size", "")
    # newsletter / write-on-medium promo banners
    raw = re.sub(r'<a href="[^"]*medium\.com/(?:blog/newsletter|write\?)[^"]*">.*?</a>', "", raw, flags=re.S)
    # strip Medium tracking query strings from in-content links
    raw = re.sub(r'(href="[^"?]+)\?source=[^"]*"', r'\1"', raw)
    return raw.strip()


def main():
    args = [a for a in sys.argv[1:] if a != "--popular"]
    popular = "--popular" in sys.argv
    export_file, slug, title, date_str, desc, tag, swatch, medium_url = args

    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)
    pub_raw = format_datetime(dt)

    article_dir = ARTICLES_DIR / slug
    article_dir.mkdir(parents=True, exist_ok=True)

    content = clean_export(Path(export_file).read_text(encoding="utf-8"))
    content = download_images(content, article_dir)
    first_img = re.search(r'<img[^>]+src="(img-[^"]+)"', content)

    meta = {
        "slug": slug,
        "title": title,
        "desc": desc,
        "tag": tag,
        "swatch": swatch,
        "popular": popular,
        "date_th": f"{TH_MONTHS[dt.month - 1]} {dt.year}",
        "pub_raw": pub_raw,
        "pub_iso": dt.isoformat(),
        "medium_url": medium_url,
        "image": first_img.group(1) if first_img else None,
    }
    (article_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (article_dir / "index.html").write_text(
        render_article_page(meta, content), encoding="utf-8")
    total = build_feed()
    print(f"Imported /articles/{slug}/ — feed.xml now has {total} items.")


if __name__ == "__main__":
    main()
