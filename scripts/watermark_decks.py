#!/usr/bin/env python3
"""Stamp a faint credit watermark on every page of the mySharing PDFs.

Re-generates the PDFs in decks/files/ from the originals in mySharing/
(git-ignored) with a subtle "© Kim Wannachar · wannachar.com" line at
the bottom of each page — visible enough to credit the source, light
enough not to disturb reading.

  ./scratchpad/pdfvenv/bin/python scripts/watermark_decks.py
"""
import io
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "mySharing"
OUT = ROOT / "decks" / "files"
FILES = ["BFF_Pattern.pdf", "CDI-OKR-2024.pdf", "NVC_V1.0.pdf",
         "BUJO-together.pdf", "SelfReflec_Workshop.pdf"]
TEXT = "© Kim Wannachar · wannachar.com"


def overlay_for(width, height):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.setFillAlpha(0.35)          # faint, non-intrusive
    c.drawRightString(width - 24, 16, TEXT)
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def stamp(src_path: Path, out_path: Path):
    reader = PdfReader(str(src_path))
    writer = PdfWriter()
    for page in reader.pages:
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        page.merge_page(overlay_for(w, h))
        writer.add_page(page)
    with open(out_path, "wb") as f:
        writer.write(f)


def main():
    for name in FILES:
        src = SRC / name
        if not src.exists():
            print(f"  skip (source missing): {name}")
            continue
        stamp(src, OUT / name)
        print(f"  watermarked: {name}")


if __name__ == "__main__":
    main()
