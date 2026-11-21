#!/usr/bin/env python3
"""Rebuild the online handbook reader (/read/) from the handbook PDF.

    python3 tools/build-reader.py "path/to/Handbook.pdf"

Run it from the repository folder whenever the handbook PDF is revised, then
commit the changes. It rewrites everything in read/ :

    read/index.html        the reader page
    read/links.css         positions of the clickable areas on each page
    read/pages/NNN.webp    one image per page (plus NNN-s.webp, a small version)
    read/park-county-good-neighbor-handbook.pdf   the download

The PDF is expected the way the designer exports it: a single cover page,
two-page spreads, and a single back cover. Spreads are cut into single pages.

Needs: poppler (pdftoppm, pdftotext), ImageMagick (magick), cwebp, and the
Python package pypdf.  On a Mac:  brew install poppler imagemagick webp
                                  python3 -m pip install pypdf
"""
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "read"
PDF_NAME = "park-county-good-neighbor-handbook.pdf"
SITE = "https://goodneighborhandbook.eastyellowstonecollaborative.org"
TITLE = "Park County Good Neighbor Handbook"
LARGE_H, SMALL_W = 1200, 800  # large page image is 1600x1200, small is 800x600


def run(*cmd):
    return subprocess.run([str(c) for c in cmd], check=True, capture_output=True, text=True).stdout


def main(pdf_path):
    pdf_path = Path(pdf_path)
    reader = PdfReader(str(pdf_path))
    boxes = [(float(p.mediabox.width), float(p.mediabox.height)) for p in reader.pages]
    single_w = min(w for w, _ in boxes)

    # Work out which book pages each PDF page holds.
    layout = []  # per PDF page: list of (book_page_number, x_offset_in_points)
    n = 0
    for w, _ in boxes:
        halves = 2 if w > single_w * 1.5 else 1
        layout.append([(n + i + 1, i * single_w) for i in range(halves)])
        n += halves
    total = n

    def book_page(pdf_index, x):
        """Book page number for a point x on a PDF page."""
        halves = layout[pdf_index]
        return halves[1][0] if len(halves) == 2 and x >= single_w else halves[0][0]

    # ---- images and text -------------------------------------------------
    pages_dir = OUT / "pages"
    if pages_dir.exists():
        shutil.rmtree(pages_dir)
    pages_dir.mkdir(parents=True)
    texts = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for i, halves in enumerate(layout):
            run("pdftoppm", "-f", i + 1, "-l", i + 1, "-scale-to-y", LARGE_H, "-scale-to-x", -1,
                "-png", "-singlefile", pdf_path, tmp / "spread")
            page_w = round(LARGE_H * single_w / boxes[i][1])
            for num, x in halves:
                png = tmp / f"{num:03d}.png"
                run("magick", tmp / "spread.png", "-crop",
                    f"{page_w}x{LARGE_H}+{round(x / single_w) * page_w}+0", "+repage", png)
                run("cwebp", "-quiet", "-q", 72, png, "-o", pages_dir / f"{num:03d}.webp")
                run("cwebp", "-quiet", "-q", 72, "-resize", SMALL_W, 0, png, "-o", pages_dir / f"{num:03d}-s.webp")
                text = run("pdftotext", "-f", i + 1, "-l", i + 1, "-r", 72, "-x", round(x), "-y", 0,
                           "-W", round(single_w), "-H", round(boxes[i][1]), pdf_path, "-")
                texts[num] = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
            print(f"  PDF page {i + 1}/{len(layout)} done", flush=True)
    shutil.copyfile(pdf_path, OUT / PDF_NAME)

    # ---- table of contents (PDF bookmarks) -------------------------------
    toc = []

    def walk(items):
        for it in items:
            if isinstance(it, list):
                walk(it)
                continue
            idx = reader.get_destination_page_number(it)
            title = str(it.title).strip()
            if title.isupper():
                title = title.title().replace(" Of ", " of ")
            toc.append((title, book_page(idx, float(it.left or 0))))

    walk(reader.outline)

    # ---- clickable areas (PDF links) -------------------------------------
    named = reader.named_destinations
    hotspots = {k: [] for k in range(1, total + 1)}
    skipped = []
    for i, page in enumerate(reader.pages):
        h = boxes[i][1]
        for annot in page.get("/Annots") or []:
            a = annot.get_object()
            if a.get("/Subtype") != "/Link":
                continue
            x0, y0, x1, y1 = (float(v) for v in a["/Rect"])
            x0, x1, y0, y1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
            num = book_page(i, (x0 + x1) / 2)
            off = dict(layout[i])[num]
            href = label = None
            action = a["/A"].get_object() if a.get("/A") is not None else None
            if action is not None and action.get("/URI"):
                uri = str(action["/URI"]).strip()
                if re.fullmatch(r"(https?://|mailto:)\S+", uri):
                    href, label = uri, re.sub(r"^(https?://|mailto:)", "", uri).rstrip("/")
                else:
                    skipped.append((num, uri))
                    continue
            else:
                dest = action.get("/D") if action is not None else a.get("/Dest")
                d = named.get(str(dest)) if dest is not None and not isinstance(dest, list) else None
                if d is None:
                    skipped.append((num, f"internal link {dest!s}"))
                    continue
                target = book_page(reader.get_destination_page_number(d), float(d.left or 0))
                href, label = f"#p{target}", f"Go to page {target}"
            hotspots[num].append(dict(
                href=href, label=label,
                left=(x0 - off) / single_w * 100, top=(h - y1) / h * 100,
                width=(x1 - x0) / single_w * 100, height=(y1 - y0) / h * 100))

    # ---- write links.css and index.html ----------------------------------
    css, items = [], []
    hid = 0
    large_w = round(LARGE_H * single_w / boxes[0][1])
    for num in range(1, total + 1):
        links = []
        for hs in hotspots[num]:
            hid += 1
            css.append(f"#h{hid}{{left:{hs['left']:.2f}%;top:{hs['top']:.2f}%;"
                       f"width:{hs['width']:.2f}%;height:{hs['height']:.2f}%}}")
            ext = "" if hs["href"].startswith("#") else ' rel="noopener"'
            links.append(f'<a class="hot" id="h{hid}" href="{html.escape(hs["href"])}"{ext}>'
                         f'<span class="sr-only">{html.escape(hs["label"])}</span></a>')
        text = "".join(f"<p>{html.escape(p)}</p>" for p in texts[num])
        items.append(
            f'      <li class="page" id="p{num}" data-page="{num}">\n'
            f'        <img src="pages/{num:03d}.webp" srcset="pages/{num:03d}-s.webp {SMALL_W}w, pages/{num:03d}.webp {large_w}w" '
            f'sizes="(max-width: 56rem) 100vw, 50vw" width="{large_w}" height="{LARGE_H}" alt="Page {num}" loading="lazy" decoding="async">\n'
            + ("        " + "".join(links) + "\n" if links else "")
            + (f'        <div class="sr-only">{text}</div>\n' if text else "")
            + "      </li>")
    (OUT / "links.css").write_text("/* Generated by tools/build-reader.py. Do not edit by hand. */\n" + "\n".join(css) + "\n")

    options = "\n".join(f'            <option value="{p}">{html.escape(t)}</option>' for t, p in toc)
    size_mb = pdf_path.stat().st_size / 1e6
    page = TEMPLATE.format(site=SITE, title=TITLE, total=total, options=options,
                           items="\n".join(items), pdf=PDF_NAME, size=f"{size_mb:.0f}")
    (OUT / "index.html").write_text(page, encoding="utf8")

    print(f"{total} pages, {len(toc)} contents entries, {hid} clickable areas.")
    if skipped:
        print("Links in the PDF that were left out because they are not usable web addresses:")
        for num, what in skipped:
            print(f"  page {num}: {what[:110]}")


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <!-- This page is generated by tools/build-reader.py. Edit that file, not this one. -->
  <title>Read the Handbook | The Good Neighbor Handbook</title>
  <meta name="description" content="Read the {title} online: a guide to living and landowning in Park County, Wyoming, from the East Yellowstone Collaborative.">
  <link rel="canonical" href="{site}/read/">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{site}/read/">
  <meta property="og:site_name" content="The Good Neighbor Handbook">
  <meta property="og:title" content="Read the {title}">
  <meta property="og:description" content="Read the handbook online or download the PDF.">
  <meta property="og:image" content="{site}/images/share.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="Cover of the {title}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="theme-color" content="#2f3240">
  <link rel="icon" href="/images/favicon-32.png" type="image/png">
  <link rel="apple-touch-icon" href="/images/apple-touch-icon.png">
  <link rel="preload" href="/fonts/arvo-700.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/css/site.css">
  <link rel="stylesheet" href="/css/reader.css">
  <link rel="stylesheet" href="/read/links.css">
  <script src="/js/reader.js"></script>
</head>
<body class="reader-page">
  <a class="skip-link" href="#main">Skip to main content</a>

  <header class="banner banner--bar">
    <!-- MENU: repeated in every page; for this page, change it in tools/build-reader.py -->
    <div class="site-header">
      <a class="site-title" href="/">
        <span class="site-title__name">The Good Neighbor Handbook</span>
        <span class="site-tagline">Park County, Wyoming</span>
      </a>
      <nav class="site-nav" aria-label="Main">
        <ul>
          <li><a href="/read/" aria-current="page">Read the Handbook</a></li>
          <li><a href="/about-us/">About Us</a></li>
          <li><a href="/get-a-copy/">Get a Copy</a></li>
        </ul>
      </nav>
    </div>
  </header>

  <main id="main" class="reader">
    <div class="reader__head">
      <h1>{title}</h1>
      <a class="reader__download" href="/read/{pdf}" download>Download the PDF <span class="reader__size">({size} MB)</span></a>
    </div>

    <div class="reader__controls" id="reader-controls" hidden>
      <label class="reader__toc">
        <span class="sr-only">Jump to section</span>
        <select id="reader-toc">
          <option value="">Contents</option>
{options}
        </select>
      </label>
      <label class="reader__slider">
        <span class="sr-only">Page</span>
        <input type="range" id="reader-slider" min="1" max="{total}" value="1" step="1">
      </label>
      <output id="reader-status" class="reader__status" aria-live="polite">Page 1 of {total}</output>
      <button type="button" id="reader-full" class="reader__button">Full screen</button>
    </div>

    <div class="reader__stage-wrap" id="reader-wrap">
      <button type="button" class="reader__arrow reader__arrow--prev" id="reader-prev" aria-label="Previous page" hidden><span aria-hidden="true">&#8249;</span></button>
      <ol class="book" id="book" data-total="{total}">
{items}
      </ol>
      <button type="button" class="reader__arrow reader__arrow--next" id="reader-next" aria-label="Next page" hidden><span aria-hidden="true">&#8250;</span></button>
    </div>
  </main>

  <footer class="site-footer">
    <p>© 2026 <a href="https://eastyellowstonecollaborative.org">East Yellowstone Collaborative</a></p>
  </footer>
</body>
</html>
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
