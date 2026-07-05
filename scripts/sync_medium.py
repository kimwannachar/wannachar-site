#!/usr/bin/env python3
"""Sync Kim Wannachar's Medium posts into this site as local article pages.

For every post in the Medium RSS feed this script:
  1. creates/refreshes /articles/<slug>/index.html with the full Thai
     content (site theme, per-article title/description/OG tags),
  2. downloads the post's images next to the page so the site owns them,
  3. writes /articles/<slug>/meta.json used to build the homepage list
     and the RSS feed,
  4. rewrites the article cards between the MEDIUM-ARTICLES markers in
     index.html to link to the local pages,
  5. regenerates /feed.xml from every article's meta.json (including
     articles imported manually, e.g. ones older than the RSS window).

Curated Thai excerpts/tags/slugs live in data/medium-overrides.json,
keyed by the Medium URL slug.
"""
import html
import json
import re
import sys
import urllib.request
from email.utils import parsedate_to_datetime, format_datetime
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
ARTICLES_DIR = ROOT / "articles"
FEED_PATH = ROOT / "feed.xml"
OVERRIDES_PATH = ROOT / "data" / "medium-overrides.json"

SITE = "https://www.wannachar.com"
FEED_URL = "https://medium.com/feed/@kimwannachar."
START_MARKER = "<!-- MEDIUM-ARTICLES:START -->"
END_MARKER = "<!-- MEDIUM-ARTICLES:END -->"
COUNT_START = "<!-- ARTICLE-COUNT:START -->"
COUNT_END = "<!-- ARTICLE-COUNT:END -->"

TH_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
             "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]

SYS_KEYWORDS = ["system-design", "backend", "engineering", "architecture",
                "software", "frugal-ai", "devops", "database", "distributed", "ai"]
MIND_KEYWORDS = ["psycholog", "leadership", "personality", "self-improvement",
                  "maslow", "team-building", "johari", "motivation",
                  "behavior", "belief", "mind"]

UA = {"User-Agent": "Mozilla/5.0"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def parse_items(xml_text: str):
    items = []
    for raw in xml_text.split("<item>")[1:]:
        body = raw.split("</item>")[0]

        def grab(pattern, default=""):
            m = re.search(pattern, body, re.S)
            return m.group(1) if m else default

        title = html.unescape(grab(r"<title><!\[CDATA\[(.*?)\]\]></title>"))
        link = grab(r"<link>(.*?)</link>").split("?")[0].strip()
        pub_raw = grab(r"<pubDate>(.*?)</pubDate>")
        categories = re.findall(r"<category><!\[CDATA\[(.*?)\]\]></category>", body)
        content = grab(r"<content:encoded><!\[CDATA\[(.*?)\]\]></content:encoded>")
        if link:
            items.append({
                "title": title,
                "link": link,
                "pub_raw": pub_raw,
                "categories": categories,
                "content": content,
            })
    return items


def excerpt_from_content(content_html: str, limit: int = 140) -> str:
    text = re.sub(r"<figure>.*?</figure>", " ", content_html, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "…"
    return text


def classify(categories, title):
    hay = " ".join(categories + [title]).lower()
    if any(k in hay for k in MIND_KEYWORDS):
        return "mind", "จิตวิทยา · Leadership"
    if any(k in hay for k in SYS_KEYWORDS):
        return "sys", "System Design"
    return "sys", "บทความ"


def thai_date(pub_raw: str) -> str:
    dt = parsedate_to_datetime(pub_raw)
    return f"{TH_MONTHS[dt.month - 1]} {dt.year}"


def medium_slug(link: str) -> str:
    return link.rstrip("/").rsplit("/", 1)[-1]


def derive_slug(link: str, override) -> str:
    if override and override.get("slug"):
        return override["slug"]
    raw = unquote(medium_slug(link))
    raw = re.sub(r"-[0-9a-f]{8,}$", "", raw)  # drop Medium's trailing hash
    tokens = re.findall(r"[a-z0-9]+", raw.lower())
    slug = "-".join(tokens)
    if not slug:
        raise ValueError(f"cannot derive slug from {link}")
    return slug


def download_images(content_html: str, article_dir: Path):
    """Download every <img> into the article dir; rewrite srcs to local files."""
    # Medium appends an invisible view-tracking pixel — drop it.
    content_html = re.sub(r'<img[^>]+src="https://medium\.com/_/stat[^"]*"[^>]*>', "", content_html)
    srcs = re.findall(r'<img[^>]+src="([^"]+)"', content_html)
    for n, src in enumerate(dict.fromkeys(srcs), start=1):
        ext = Path(src.split("?")[0]).suffix.lower()
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            ext = ".png"
        local = article_dir / f"img-{n}{ext}"
        if not local.exists():
            try:
                req = urllib.request.Request(src, headers=UA)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    local.write_bytes(resp.read())
            except Exception as e:  # keep remote URL if download fails
                print(f"  warn: could not download {src}: {e}", file=sys.stderr)
                continue
        content_html = content_html.replace(src, local.name)
    return content_html


ARTICLE_CSS = """
  :root{
    --paper:#FDF9FA;--pink:#F4D6E0;--pink-soft:#FAEBF0;--pink-deep:#DFA8BC;
    --navy:#22304E;--navy-soft:#5D6A85;--navy-deep:#16213A;--line:#EDDFE4;--max:720px;
  }
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Anuphan',sans-serif;background:var(--paper);color:var(--navy);line-height:1.85}
  a{color:inherit}
  .wrap{max-width:var(--max);margin:0 auto;padding:0 24px}
  nav{position:sticky;top:0;z-index:10;background:rgba(253,249,250,.92);
    backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
  .nav-inner{display:flex;align-items:center;justify-content:space-between;height:64px}
  .logo{font-family:'Trirong',serif;font-size:1.12rem;font-weight:500;
    letter-spacing:.06em;text-decoration:none}
  .logo span{color:var(--pink-deep)}
  .back{font-size:.9rem;color:var(--navy-soft);text-decoration:none}
  .back:hover{color:var(--navy-deep);text-decoration:underline}
  main{padding:64px 0 80px}
  .a-head{margin-bottom:40px}
  .a-tag{font-size:.7rem;font-weight:600;letter-spacing:.18em;text-transform:uppercase;
    color:var(--navy-soft)}
  .a-tag.mind{color:#B0728C}
  h1{font-family:'Trirong',serif;font-size:clamp(1.6rem,4.4vw,2.3rem);line-height:1.55;
    font-weight:400;color:var(--navy-deep);margin:12px 0 14px}
  .a-meta{font-family:'Trirong',serif;font-style:italic;font-size:.9rem;color:var(--navy-soft)}
  .content{margin-top:8px}
  .content p{margin:20px 0}
  .content h3,.content h4{font-family:'Trirong',serif;font-weight:500;
    color:var(--navy-deep);margin:36px 0 6px;line-height:1.6}
  .content h3{font-size:1.35rem}
  .content h4{font-size:1.12rem}
  .content ul,.content ol{margin:20px 0;padding-left:26px}
  .content li{margin:8px 0}
  .content figure{margin:32px 0}
  .content img{max-width:100%;height:auto;display:block;margin:0 auto}
  .content figcaption{text-align:center;font-size:.82rem;color:var(--navy-soft);
    margin-top:10px;font-style:italic}
  .content blockquote{border-left:3px solid var(--pink-deep);background:var(--pink-soft);
    padding:16px 22px;margin:28px 0;color:var(--navy-deep)}
  .content pre{background:var(--navy-deep);color:#EFE6EA;padding:18px 20px;
    overflow-x:auto;font-size:.85rem;line-height:1.6;margin:24px 0}
  .content code{font-family:ui-monospace,Menlo,monospace}
  .content a{color:var(--navy-deep);text-decoration:underline;
    text-decoration-color:var(--pink-deep);text-underline-offset:3px}
  .content hr{border:0;border-top:1px solid var(--line);margin:36px 0}
  .a-foot{margin-top:56px;padding-top:24px;border-top:1px solid var(--line);
    font-size:.88rem;color:var(--navy-soft)}
  .a-foot a{color:var(--navy-deep)}
  footer{border-top:1px solid var(--line);padding:36px 0;background:var(--navy-deep);color:#EFE6EA}
  .foot-inner{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;font-size:.85rem}
  .foot-inner a{color:#EFE6EA;text-decoration:none}
  .foot-inner a:hover{text-decoration:underline;color:var(--pink)}
"""


def render_article_page(meta, content_html):
    esc = lambda s: html.escape(s, quote=False)
    esc_attr = lambda s: html.escape(s, quote=True)
    og_image = (f"{SITE}/articles/{meta['slug']}/{meta['image']}"
                if meta.get("image") else f"{SITE}/kim-avatar.png")
    tag_class = "a-tag mind" if meta["swatch"] == "mind" else "a-tag"
    return f'''<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(meta["title"])} — Kim Wannachar</title>
<meta name="description" content="{esc_attr(meta["desc"])}">
<meta property="og:title" content="{esc_attr(meta["title"])}">
<meta property="og:description" content="{esc_attr(meta["desc"])}">
<meta property="og:image" content="{esc_attr(og_image)}">
<meta property="og:url" content="{SITE}/articles/{meta["slug"]}/">
<meta property="og:type" content="article">
<meta property="og:locale" content="th_TH">
<link rel="canonical" href="{SITE}/articles/{meta["slug"]}/">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="alternate" type="application/rss+xml" title="Kim Wannachar" href="/feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Trirong:ital,wght@0,300;0,400;0,500;1,300&family=Anuphan:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>{ARTICLE_CSS}</style>
</head>
<body>

<nav>
  <div class="wrap nav-inner">
    <a class="logo" href="/">Kim <span>Wannachar</span></a>
    <a class="back" href="/#articles">← บทความทั้งหมด</a>
  </div>
</nav>

<main>
  <article class="wrap">
    <div class="a-head">
      <span class="{tag_class}">{esc(meta["tag"])}</span>
      <h1>{esc(meta["title"])}</h1>
      <div class="a-meta">{meta["date_th"]}</div>
    </div>
    <div class="content">
{content_html}
    </div>
    <div class="a-foot">
      บทความนี้เผยแพร่ครั้งแรกบน <a href="{esc_attr(meta["medium_url"])}" target="_blank" rel="noopener">Medium</a>
    </div>
  </article>
</main>

<footer>
  <div class="wrap foot-inner">
    <span>© 2026 Kim Wannachar</span>
    <a href="/">wannachar.com</a>
  </div>
</footer>

</body>
</html>
'''


def render_card(meta):
    esc = lambda s: html.escape(s, quote=False)
    pop_html = '<span class="pop">👏 ยอดนิยม</span>' if meta.get("popular") else ''
    return f'''    <article class="article">
      <div class="swatch sw-{meta["swatch"]}" aria-hidden="true"></div>
      <div>
        <h3><a href="/articles/{meta["slug"]}/">{esc(meta["title"])}</a>{pop_html}</h3>
        <p>{esc(meta["desc"])}</p>
        <span class="tag tag-{meta["swatch"]}">{esc(meta["tag"])}</span>
      </div>
      <span class="meta">{meta["date_th"]}</span>
    </article>'''


def build_feed():
    metas = []
    for meta_file in ARTICLES_DIR.glob("*/meta.json"):
        metas.append(json.loads(meta_file.read_text(encoding="utf-8")))
    metas.sort(key=lambda m: m["pub_iso"], reverse=True)
    items = []
    for m in metas:
        pub = format_datetime(parsedate_to_datetime(m["pub_raw"]))
        items.append(f"""    <item>
      <title><![CDATA[{m['title']}]]></title>
      <link>{SITE}/articles/{m['slug']}/</link>
      <guid isPermaLink="true">{SITE}/articles/{m['slug']}/</guid>
      <description><![CDATA[{m['desc']}]]></description>
      <pubDate>{pub}</pubDate>
    </item>""")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Kim Wannachar — นักอ่านที่อยากเป็นนักเขียน</title>
    <link>{SITE}/</link>
    <description>บทความ system design จิตวิทยา และ leadership ภาษาไทย</description>
    <language>th</language>
    <atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml"/>
{chr(10).join(items)}
  </channel>
</rss>
"""
    FEED_PATH.write_text(feed, encoding="utf-8")
    return len(metas)


def process_item(item, overrides):
    override = overrides.get(medium_slug(item["link"]))
    slug = derive_slug(item["link"], override)
    swatch, tag_default = classify(item["categories"], item["title"])
    if override:
        desc = override.get("desc_th") or excerpt_from_content(item["content"])
        tag = override.get("tag_th", tag_default)
        swatch = override.get("swatch", swatch)
    else:
        desc = excerpt_from_content(item["content"])
        tag = tag_default

    article_dir = ARTICLES_DIR / slug
    article_dir.mkdir(parents=True, exist_ok=True)
    content_html = download_images(item["content"], article_dir)

    first_img = re.search(r'<img[^>]+src="(img-[^"]+)"', content_html)
    dt = parsedate_to_datetime(item["pub_raw"])
    meta = {
        "slug": slug,
        "title": item["title"],
        "desc": desc,
        "tag": tag,
        "swatch": swatch,
        "popular": bool(override and override.get("popular")),
        "date_th": thai_date(item["pub_raw"]),
        "pub_raw": item["pub_raw"],
        "pub_iso": dt.isoformat(),
        "medium_url": item["link"],
        "image": first_img.group(1) if first_img else None,
    }
    (article_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (article_dir / "index.html").write_text(
        render_article_page(meta, item["content"] and content_html), encoding="utf-8")
    return meta


def main():
    xml_text = fetch(FEED_URL).decode("utf-8")
    items = parse_items(xml_text)
    if not items:
        print("No items found in feed; nothing changed.", file=sys.stderr)
        sys.exit(1)

    overrides = {}
    if OVERRIDES_PATH.exists():
        overrides = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))

    fresh = [process_item(item, overrides) for item in items]

    # The homepage is a showroom of EVERY article — feed items plus any
    # manually imported ones — sorted newest first.
    all_metas = [json.loads(f.read_text(encoding="utf-8"))
                 for f in ARTICLES_DIR.glob("*/meta.json")]
    all_metas.sort(key=lambda m: m["pub_iso"], reverse=True)

    html_text = INDEX.read_text(encoding="utf-8")
    if START_MARKER not in html_text or END_MARKER not in html_text:
        print("Markers not found in index.html", file=sys.stderr)
        sys.exit(1)
    new_section = "\n\n".join(render_card(m) for m in all_metas)
    pattern = re.compile(re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.S)
    html_text = pattern.sub(
        f"{START_MARKER}\n{new_section}\n    {END_MARKER}", html_text)
    count_pattern = re.compile(re.escape(COUNT_START) + r".*?" + re.escape(COUNT_END), re.S)
    html_text = count_pattern.sub(
        f"{COUNT_START}ทั้งหมด {len(all_metas)} บทความ{COUNT_END}", html_text)
    INDEX.write_text(html_text, encoding="utf-8")

    total = build_feed()
    print(f"Refreshed {len(fresh)} pages from the feed; homepage and "
          f"feed.xml now list {total} articles.")


if __name__ == "__main__":
    main()
