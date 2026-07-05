#!/usr/bin/env python3
"""Bulk-import a full Medium archive export into /articles/<slug>/.

Medium's RSS feed only exposes the 10 most recent posts, so the daily
sync can never reach older articles. This one-off importer ingests the
official "Download your information" export (Settings → Download your
information → .zip), which contains every published post as a clean
HTML file under posts/.

  python3 scripts/import_medium_archive.py <unzipped-export-dir>

It skips posts already on the site (matched by Medium postId), skips a
short exclude-list of quote-only responses, converts Medium's "graf"
HTML to the site's article markup, downloads images locally, and writes
/articles/<slug>/index.html + meta.json. Run scripts/sync_medium.py
afterwards to rebuild the homepage list, article count, and feed.xml.
"""
import html
import json
import re
import sys
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_medium import (ARTICLES_DIR, classify, download_images,
                         render_article_page, thai_date)

# Posts to keep off the site, excluded by Medium postId:
#   3163d3328619, 64aacdd974f6 — quote-only responses, not real articles
#   bdd248e16ef9 — "42 ข้อ~" personal post the owner is removing from Medium
EXCLUDE_IDS = {"3163d3328619", "64aacdd974f6", "bdd248e16ef9"}

ALLOWED = {"p", "h3", "h4", "ul", "ol", "li", "blockquote", "figure",
           "figcaption", "img", "pre", "code", "strong", "em", "br", "hr", "a"}


def existing_postids():
    ids = {}
    for mf in ARTICLES_DIR.glob("*/meta.json"):
        m = json.loads(mf.read_text(encoding="utf-8"))
        pid = m["medium_url"].rstrip("/").split("-")[-1]
        ids[pid] = m["slug"]
    return ids


def post_id(path: Path) -> str:
    return path.stem.split("-")[-1]


def clean_graf_html(body: str) -> str:
    """Convert Medium export body HTML to the site's article subset."""
    # cut Medium's export footer ("By kimwannachar on … Exported from Medium")
    body = re.split(r"<footer", body, maxsplit=1)[0]
    # drop the duplicated title heading (page renders its own <h1>)
    body = re.sub(r"<h3[^>]*graf--title[^>]*>.*?</h3>", "", body, flags=re.S)
    # section dividers → horizontal rule
    body = re.sub(r'<div class="section-divider">.*?</div>', "<hr>", body, flags=re.S)
    # normalise pull/block quotes to <blockquote>
    body = re.sub(r"<blockquote[^>]*>", "<blockquote>", body)
    # keep only src on images
    body = re.sub(r"<img[^>]*\bsrc=\"([^\"]+)\"[^>]*>", r'<img src="\1" alt="">', body)
    # keep only href on links, strip Medium tracking query
    def fix_a(m):
        href = re.sub(r"\?source=[^\"]*", "", m.group(1))
        return f'<a href="{href}">'
    body = re.sub(r'<a[^>]*\bhref="([^"]+)"[^>]*>', fix_a, body)

    # strip attributes from all other allowed tags; drop disallowed tags
    def strip_tag(m):
        closing = m.group(1) == "/"
        name = m.group(2).lower()
        if name not in ALLOWED:
            return ""
        if name == "img" or name == "a":
            return m.group(0)  # already normalised above
        return f"</{name}>" if closing else f"<{name}>"
    body = re.sub(r"<(/?)([a-zA-Z0-9]+)[^>]*>", strip_tag, body)

    # tidy: drop empty paragraphs/headings, collapse whitespace runs
    body = re.sub(r"<(p|h3|h4|li|blockquote)>\s*</\1>", "", body)
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def derive_slug(title: str, pid: str, taken: set) -> str:
    tokens = re.findall(r"[a-z0-9]+", title.lower())
    slug = "-".join(tokens)[:60].strip("-")
    if not slug:
        slug = f"story-{pid}"      # pure-Thai title → stable postId slug
    base, n = slug, 2
    while slug in taken:
        slug = f"{base}-{n}"
        n += 1
    taken.add(slug)
    return slug


def main():
    export_dir = Path(sys.argv[1])
    posts_dir = export_dir / "posts"
    files = sorted(p for p in posts_dir.glob("*.html")
                   if re.match(r"\d{4}-\d{2}-\d{2}_", p.name))

    existing = existing_postids()
    taken = set(existing.values())
    imported = skipped = excluded = 0

    for path in files:
        pid = post_id(path)
        if pid in existing:
            skipped += 1
            continue
        if pid in EXCLUDE_IDS:
            excluded += 1
            continue

        h = path.read_text(encoding="utf-8")
        title = html.unescape(re.search(r"<title>(.*?)</title>", h, re.S).group(1)).strip()
        dt_raw = re.search(r'class="dt-published"[^>]*datetime="([^"]+)"', h)
        dt = datetime.fromisoformat(dt_raw.group(1).replace("Z", "+00:00"))
        body = re.search(r'class="e-content">(.*)', h, re.S).group(1)

        content = clean_graf_html(body)
        slug = derive_slug(title, pid, taken)
        article_dir = ARTICLES_DIR / slug
        article_dir.mkdir(parents=True, exist_ok=True)
        content = download_images(content, article_dir)
        first_img = re.search(r'<img[^>]+src="(img-[^"]+)"', content)
        swatch, tag = classify([], title)

        # excerpt: first paragraph text, trimmed
        para = re.search(r"<p>(.*?)</p>", content, re.S)
        desc = re.sub(r"<[^>]+>", "", para.group(1)) if para else title
        desc = re.sub(r"\s+", " ", html.unescape(desc)).strip()
        if len(desc) > 150:
            desc = desc[:150].rsplit(" ", 1)[0] + "…"

        meta = {
            "slug": slug, "title": title, "desc": desc, "tag": tag,
            "swatch": swatch, "popular": False,
            "date_th": thai_date(format_datetime(dt)),
            "pub_raw": format_datetime(dt), "pub_iso": dt.isoformat(),
            "medium_url": f"https://medium.com/@kimwannachar./{path.stem.split('_',1)[1]}",
            "image": first_img.group(1) if first_img else None,
        }
        (article_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        (article_dir / "index.html").write_text(
            render_article_page(meta, content), encoding="utf-8")
        imported += 1

    print(f"Imported {imported} new articles "
          f"({skipped} already on site, {excluded} responses excluded).")
    print("Now run: python3 scripts/sync_medium.py")


if __name__ == "__main__":
    main()
