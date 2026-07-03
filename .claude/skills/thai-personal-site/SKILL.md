---
name: thai-personal-site
description: Conventions for building and maintaining the owner's Thai-language personal website and article blog (book-style landing page inspired by samnewman.io). Use this skill whenever working on this website project — creating pages, writing HTML/CSS, adding articles, structuring URLs, or handling anything related to site layout, typography, i18n, or SEO. Applies even if the request doesn't mention "Thai" or "blog" explicitly.
---

# Thai-First Personal Site

Personal website + article blog for a tech Platform Lead. Content strategy: **Thai-only articles now, structured so English can be added later without restructuring.** Do not build a full bilingual site. Do not add language switchers to article pages.

## Language rules

1. **All article content and article-facing UI is Thai.** Navigation labels, dates, section headings on Thai pages: Thai.
2. Set `<html lang="th">` on all Thai pages. If an English page exists (About only, see below), that page uses `lang="en"`.
3. **The About page is the one exception**: maintain both `/about/` (Thai) and `/en/about/` (English). These are the only pages under `/en/`. Cross-link them with a small text link ("English" / "ภาษาไทย"), not a global language switcher.
4. Never machine-translate articles or generate English versions of Thai articles unless the owner explicitly asks. If they later want English content, treat it as a separate article, not a translation pair.

## URL structure (future-proofing, decide once)

- Thai content lives at the **root**: `/articles/slug-name/`, `/about/`, `/` — no `/th/` prefix. Root = Thai forever; do not migrate Thai content under a prefix later.
- Reserve `/en/` for future English content. Nothing needs to exist there now except `/en/about/`.
- Slugs are **lowercase English/romanized**, hyphen-separated (e.g. `/articles/ai-augmented-agile-delivery/`), never Thai script or URL-encoded Thai. Thai script in URLs breaks sharing previews and looks like percent-garbage when pasted.
- Add `hreflang` tags only on the About pair (`th` ↔ `en`). Do not add hreflang anywhere else.

## Thai typography & rendering

- Font stack must include proper Thai support. Prefer: `"IBM Plex Sans Thai"`, `"Noto Sans Thai"`, or `"Sarabun"` from Google Fonts, with system fallbacks. Never rely on a Latin-only webfont with Thai falling through to default — mismatched Thai/Latin weights look broken.
- `line-height` for Thai body text: **1.7–1.9** (Thai has tall vowel/tone marks above and below the baseline; 1.5 clips or crowds them).
- Do NOT use `text-transform: uppercase` styling patterns as design elements for Thai text; use size/weight/color instead.
- Avoid `word-break: break-all`. Thai has no spaces between words; use `line-break: normal` and let the browser's Thai segmenter work. If line-breaking looks wrong, `word-break: keep-all` on Thai is harmful — leave defaults.
- Justified text (`text-align: justify`) usually looks bad in Thai; use left-align.
- Dates on Thai pages: Thai format, Buddhist Era optional but be consistent (e.g. "3 กรกฎาคม 2569" or "3 ก.ค. 2026" — pick one and stick to it site-wide).

## Design direction

- Book-style, editorial landing page in the spirit of samnewman.io: generous whitespace, strong typographic hierarchy, minimal chrome, content-first.
- Static HTML/CSS preferred; no framework unless the owner asks. If a static site generator is requested, default to one with clean Thai/multilingual support (e.g. Hugo or Astro) and keep the root-Thai / `/en/`-reserved structure above.
- Mobile-first; most Thai readers arrive from LINE/Facebook shares on phones.

## SEO & sharing

- Every article: Thai `<title>`, Thai `meta description`, Open Graph tags (`og:title`, `og:description`, `og:image`, `og:locale` = `th_TH`).
- Generate an `og:image` per article or a site default — link previews matter for LINE/Facebook distribution.
- RSS/Atom feed for articles is required.

## When adding a new article

1. Create `/articles/<english-slug>/` with the Thai content.
2. Fill title, description, date (consistent format), OG tags.
3. Update the article index page and the feed.
4. Do not create any `/en/` counterpart.
