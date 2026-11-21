#!/usr/bin/env python3
"""Rebuild the online handbook reader (public/read/) from the handbook PDF.

    python3 tools/build-reader.py "path/to/Handbook.pdf"

Run it from the repository folder whenever the handbook PDF is revised, then
commit the changes. It replaces everything in public/read/ :

    index.html        the reader page
    links.css         positions of the clickable areas on each page
    pages/NNN.webp    one image per page, in three sizes (-s small, -l large)
    park-county-good-neighbor-handbook.pdf   the download

The PDF is expected the way the designer exports it: landscape 4:3 pages, with
a single cover page, two-page spreads, and a single back cover. Spreads are
cut into single pages. If the PDF does not look like that the script stops
and says why, without touching the existing reader.

Needs: poppler (pdftoppm, pdftotext), ImageMagick (magick), cwebp, and the
Python package pypdf (built with pypdf 7, poppler 25, cwebp 1.6). On a Mac:

    brew install poppler imagemagick webp
    python3 -m venv .venv && .venv/bin/pip install pypdf
    .venv/bin/python tools/build-reader.py "path/to/Handbook.pdf"
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
OUT = ROOT / "public" / "read"
PDF_NAME = "park-county-good-neighbor-handbook.pdf"
SITE = "https://goodneighborhandbook.eastyellowstonecollaborative.org"
TITLE = "Park County Good Neighbor Handbook"
SIZES = (("-s", 800), ("", 1600), ("-l", 2400))  # image widths; heights follow 4:3
FOOTER_BAND = 0.08  # bottom share of each page holding the running footer


def run(*cmd):
    return subprocess.run([str(c) for c in cmd], check=True, capture_output=True, text=True).stdout


def stop(message):
    sys.exit("Not rebuilt: " + message)


def main(pdf_path):
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        stop(f"cannot find {pdf_path}")
    reader = PdfReader(str(pdf_path))
    boxes = [(float(p.mediabox.width), float(p.mediabox.height)) for p in reader.pages]
    single_w = min(w for w, _ in boxes)
    page_h = boxes[0][1]

    # ---- check the PDF is the shape the reader is built for --------------
    for i, (page, (w, h)) in enumerate(zip(reader.pages, boxes), 1):
        if int(page.get("/Rotate") or 0) % 360:
            stop(f"PDF page {i} is rotated.")
        if any(abs(float(a) - float(b)) > 0.5 for a, b in zip(page.cropbox, page.mediabox)):
            stop(f"PDF page {i} has a crop box different from its page size.")
        if abs(h - page_h) > 1 or min(abs(w - single_w), abs(w - 2 * single_w)) > 1:
            stop(f"PDF page {i} is {w:.0f}x{h:.0f} points; expected {single_w:.0f} or "
                 f"{2 * single_w:.0f} wide and {page_h:.0f} high.")
    if abs(single_w / page_h - 4 / 3) > 0.01:
        stop(f"pages are {single_w:.0f}x{page_h:.0f} points. The reader is laid out for 4:3 pages; "
             "css/reader.css would need its aspect ratios changed for another shape.")

    # Which book pages each PDF page holds.
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

    def text_in(pdf_index, x, y_top, w, h):
        """Text inside a rectangle (points, measured from the top-left of the PDF page)."""
        out = run("pdftotext", "-f", pdf_index + 1, "-l", pdf_index + 1, "-r", 72, "-x", round(x),
                  "-y", round(y_top), "-W", max(1, round(w)), "-H", max(1, round(h)), pdf_path, "-")
        return out.replace("\f", "")

    # Everything is built in a scratch folder and swapped in at the end, so a
    # failure part-way leaves the existing reader untouched.
    build = OUT.with_name("read.building")
    if build.exists():
        shutil.rmtree(build)
    (build / "pages").mkdir(parents=True)

    # ---- images and text -------------------------------------------------
    large_w = SIZES[-1][1]
    large_h = round(large_w * page_h / single_w)
    texts = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for i, halves in enumerate(layout):
            run("pdftoppm", "-f", i + 1, "-l", i + 1, "-scale-to-y", large_h, "-scale-to-x", -1,
                "-png", "-singlefile", pdf_path, tmp / "spread")
            for num, x in halves:
                png = tmp / f"{num:03d}.png"
                run("magick", tmp / "spread.png", "-crop",
                    f"{large_w}x{large_h}+{round(x / single_w) * large_w}+0", "+repage", png)
                for suffix, width in SIZES:
                    args = ["-q", 68] if width == large_w else ["-q", 72, "-resize", width, 0]
                    run("cwebp", "-quiet", *args, png, "-o", build / "pages" / f"{num:03d}{suffix}.webp")
                # Leave out the running footer and page number at the bottom of the page.
                text = text_in(i, x, 0, single_w, page_h * (1 - FOOTER_BAND))
                texts[num] = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
            print(f"  PDF page {i + 1}/{len(layout)} done", flush=True)
    shutil.copyfile(pdf_path, build / PDF_NAME)

    # ---- table of contents (PDF bookmarks) -------------------------------
    toc = []

    def walk(items):
        for it in items:
            if isinstance(it, list):
                walk(it)
                continue
            idx = reader.get_destination_page_number(it)
            if idx is None or idx < 0:
                continue
            title = str(it.title).strip()
            if title.isupper():
                title = title.title().replace(" Of ", " of ")
            toc.append((title, book_page(idx, float(it.left or 0))))

    walk(reader.outline)
    section_at = {page: title for title, page in toc}

    # ---- clickable areas (PDF links) -------------------------------------
    named = reader.named_destinations
    links = {k: [] for k in range(1, total + 1)}  # page -> [{href, external, boxes:[...], words:[...]}]
    skipped = []
    for i, page in enumerate(reader.pages):
        for annot in page.get("/Annots") or []:
            a = annot.get_object()
            if a.get("/Subtype") != "/Link" or a.get("/Rect") is None:
                continue
            x0, y0, x1, y1 = (float(v) for v in a["/Rect"])
            x0, x1, y0, y1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
            num = book_page(i, (x0 + x1) / 2)
            off = dict(layout[i])[num]
            action = a["/A"].get_object() if a.get("/A") is not None else None
            if action is not None and action.get("/URI"):
                uri = str(action["/URI"]).strip()
                if re.match(r"www\.", uri, re.I):
                    uri = "https://" + uri
                # An e-mail address typed as a web address, e.g. http://name@example.com
                m = re.fullmatch(r"https?://([^/@\s]+@[^/@\s]+\.[a-z]{2,})/?", uri, re.I)
                if m:
                    uri = "mailto:" + m.group(1)
                if not re.fullmatch(r"(https?://|mailto:|tel:)\S+", uri, re.I):
                    skipped.append((num, uri))
                    continue
                href, external = uri, True
            else:
                dest = action.get("/D") if action is not None else a.get("/Dest")
                try:
                    if isinstance(dest, list):
                        idx = reader.get_page_number(dest[0].get_object())
                        left = float(dest[2] or 0) if len(dest) > 2 else 0.0
                    else:
                        d = named[str(dest)]
                        idx, left = reader.get_destination_page_number(d), float(d.left or 0)
                    target = book_page(idx, left)
                except Exception:
                    skipped.append((num, f"internal link {dest!s}"))
                    continue
                href, external = f"#p{target}", False
            box = dict(left=x0 - off, top=page_h - y1, width=x1 - x0, height=y1 - y0)
            words = re.sub(r"\s+", " ", text_in(i, x0 - 1, page_h - y1 - 1, x1 - x0 + 2, y1 - y0 + 2)).strip()
            # A link that wraps over several lines is several rectangles in the
            # PDF; keep them together as one link.
            prev = links[num][-1] if links[num] else None
            if prev and prev["href"] == href:
                prev["boxes"].append(box)
                prev["words"].append(words)
            else:
                links[num].append(dict(href=href, external=external, boxes=[box], words=[words]))

    # Make each area as tall as the spacing between lines allows (easier to hit).
    for num, page_links in links.items():
        all_boxes = [b for l in page_links for b in l["boxes"]]
        grown = []
        for b in all_boxes:
            above = below = None
            for o in all_boxes:
                if o is b or o["left"] >= b["left"] + b["width"] or o["left"] + o["width"] <= b["left"]:
                    continue
                if o["top"] + o["height"] <= b["top"] + 0.5:
                    gap = b["top"] - (o["top"] + o["height"])
                    above = gap if above is None else min(above, gap)
                elif o["top"] >= b["top"] + b["height"] - 0.5:
                    gap = o["top"] - (b["top"] + b["height"])
                    below = gap if below is None else min(below, gap)
            pad = b["height"] * 0.4
            up = max(0, min(above / 2, pad * 2)) if above is not None else pad
            down = max(0, min(below / 2, pad * 2)) if below is not None else pad
            grown.append((up, down))
        for b, (up, down) in zip(all_boxes, grown):
            b["top"] = max(0, b["top"] - up)
            b["height"] = min(page_h - b["top"], b["height"] + up + down)

    def label_for(link):
        words = " ".join(w for w in link["words"] if w).strip()
        if not link["external"]:
            target = int(link["href"][2:])
            name = section_at.get(target) or words
            return f"{name}, page {target}" if name else f"Go to page {target}"
        shown = re.sub(r"^(https?://|mailto:|tel:)", "", link["href"], flags=re.I)
        shown = re.sub(r"[?#].*$", "", shown).replace("%40", "@").replace("%20", " ").rstrip("/")
        if not re.search(r"[A-Za-z]{3}", words) or len(words) > 120:
            words = shown
        if link["href"].lower().startswith(("mailto:", "tel:")):
            return words
        return words + " (opens in a new tab)"

    # ---- write links.css and index.html ----------------------------------
    css, items = [], []
    hid = areas = 0
    med_w = SIZES[1][1]
    med_h = round(med_w * page_h / single_w)

    def srcset(num):
        return ", ".join(f"pages/{num:03d}{suffix}.webp {width}w" for suffix, width in SIZES)

    for num in range(1, total + 1):
        anchors = []
        for link in links[num]:
            areas += 1
            ids = []
            for b in link["boxes"]:
                hid += 1
                ids.append(hid)
                css.append(f"#h{hid}{{left:{b['left'] / single_w * 100:.2f}%;top:{b['top'] / page_h * 100:.2f}%;"
                           f"width:{b['width'] / single_w * 100:.2f}%;height:{b['height'] / page_h * 100:.2f}%}}")
            attrs = ' target="_blank" rel="noopener"' if link["href"].lower().startswith("http") else ""
            label = f'<span class="sr-only">{html.escape(label_for(link))}</span>'
            href = html.escape(link["href"], quote=True)
            if len(ids) == 1:
                anchors.append(f'<a class="hot" id="h{ids[0]}" href="{href}"{attrs}>{label}</a>')
            else:
                spans = "".join(f'<span class="hot" id="h{i}"></span>' for i in ids)
                anchors.append(f'<a class="hot-group" href="{href}"{attrs}>{spans}{label}</a>')
        text = "".join(f"<p>{html.escape(p)}</p>" for p in texts[num])
        items.append(
            f'      <li class="page" id="p{num}" data-page="{num}">\n'
            f'        <img src="pages/{num:03d}.webp" srcset="{srcset(num)}" '
            f'sizes="(max-width: 68rem) 100vw, 50vw" width="{med_w}" height="{med_h}" alt="Page {num}" loading="lazy" decoding="async">\n'
            + ("        " + "".join(anchors) + "\n" if anchors else "")
            + (f'        <div class="sr-only">{text}</div>\n' if text else "")
            + "      </li>")
    (build / "links.css").write_text(
        "/* Generated by tools/build-reader.py. Do not edit by hand. */\n" + "\n".join(css) + "\n")

    if toc:
        first = min(p for _, p in toc)
        opts = ([(1, "Cover")] if first > 1 else []) + [(p, t) for t, p in toc]
        options = "\n".join(f'            <option value="{p}">{html.escape(t)}</option>' for p, t in opts)
        contents = CONTENTS.format(options=options)
    else:
        contents = ""
    size_mb = pdf_path.stat().st_size / 1e6
    (build / "index.html").write_text(
        TEMPLATE.format(site=SITE, title=TITLE, total=total, contents=contents,
                        items="\n".join(items), pdf=PDF_NAME, size=f"{size_mb:.0f}"), encoding="utf8")

    if OUT.exists():
        shutil.rmtree(OUT)
    build.rename(OUT)

    print(f"{total} pages, {len(toc)} contents entries, {areas} links.")
    if skipped:
        print("\n*** LINKS LEFT OUT ***")
        print("These links in the PDF are not usable web addresses, so they are not clickable in")
        print("the reader. Fix them in the PDF and run this again:")
        for num, what in skipped:
            print(f"  page {num}: {what[:110]}")


CONTENTS = """      <label class="reader__toc">
        <span class="sr-only">Section</span>
        <select id="reader-toc">
{options}
        </select>
      </label>
"""

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

  <div class="reader-screen">
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
    <p class="sr-only">If you use a screen reader, the PDF download is the best way to read the handbook: it is tagged so that headings and text are read in the right order. The page text included below is extracted automatically and may be out of order.</p>

    <div class="reader__stage-wrap" id="reader-wrap">
      <button type="button" class="reader__arrow reader__arrow--prev" id="reader-prev" aria-label="Previous page"><span aria-hidden="true">&#8249;</span></button>
      <div class="reader__viewport" id="reader-viewport">
      <ol class="book" id="book" data-total="{total}">
{items}
      </ol>
      </div>
      <button type="button" class="reader__arrow reader__arrow--next" id="reader-next" aria-label="Next page"><span aria-hidden="true">&#8250;</span></button>
    </div>

    <div class="reader__controls" id="reader-controls">
{contents}      <label class="reader__slider">
        <span class="sr-only">Page</span>
        <input type="range" id="reader-slider" min="1" max="{total}" value="1" step="1">
      </label>
      <output id="reader-status" class="reader__status" aria-live="polite">Page 1 of {total}</output>
      <span class="reader__zoom" role="group" aria-label="Zoom">
        <button type="button" id="reader-zoom-out" class="reader__button" aria-label="Zoom out" disabled>&minus;</button>
        <button type="button" id="reader-zoom-in" class="reader__button" aria-label="Zoom in">+</button>
      </span>
      <button type="button" id="reader-full" class="reader__button">Full screen</button>
      <a class="reader__download reader__download--bar" href="/read/{pdf}" download>Download the PDF <span class="reader__size">({size} MB)</span></a>
    </div>
  </main>
  </div>

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
