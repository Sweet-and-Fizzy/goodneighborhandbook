# The Good Neighbor Handbook website

https://goodneighborhandbook.eastyellowstonecollaborative.org

Plain HTML and CSS. There is no build step and nothing to install. Netlify
publishes the `main` branch as-is.

## Where things are

| To change | Edit |
| --- | --- |
| Home page headline and buttons | `index.html` |
| About Us text, contributors, funding partners | `about-us/index.html` |
| Pickup locations and contact person | `get-a-copy/index.html` |
| "Page not found" page | `404.html` |
| The online handbook reader | generated, see "Updating the handbook" below |
| Colors, fonts, spacing | `css/site.css` |

Editable sections are marked with `<!-- EDIT: ... -->` comments.

## Things that are repeated in more than one file

There is no shared template, so these have to be changed everywhere they appear.

- **The menu** is in all four `.html` files, and in `tools/build-reader.py` for
  the reader page.
- **The footer and its year** are in `index.html`, `about-us/index.html` and
  `get-a-copy/index.html`.
- **Page title and description.** The lines near the top of each page
  (`<title>`, `description`, and the `og:` lines) are what search engines and
  link previews show. Update them when the page content changes.
- **The site address** appears near the top of the three main pages, in
  `robots.txt` and in `sitemap.xml`. It only matters if the domain changes.

Adding a new page means copying an existing page folder, adding it to the menu
in all four files and in `tools/build-reader.py`, and adding a line to
`sitemap.xml`.

## Updating the handbook

The reader at `/read/` is generated from the handbook PDF: one image per page,
the contents menu from the PDF's bookmarks, and the clickable areas from the
PDF's links. Do not edit the files in `read/` by hand. When the handbook is
revised, run this from the repository folder and commit everything it changes:

    python3 tools/build-reader.py "path/to/the-new-handbook.pdf"

The script expects the PDF as the designer exports it (a cover page, two-page
spreads, a back cover). What it needs installed is listed at the top of the
script. The reader's behaviour is in `js/reader.js` and its look in
`css/reader.css`.

## Making a change on GitHub

1. Open the file and click the pencil icon.
2. Make the edit, then choose "Create a new branch and start a pull request".
3. Netlify adds a preview link to the pull request. Check the page there.
4. Once the pull request is merged, the live site updates within a minute.

## Previewing on your own computer

Links start with `/`, so open the site through a local server rather than
double-clicking the files. From this folder, run:

    python3 -m http.server 8000

Then visit http://localhost:8000. The "page not found" page, the redirects and
the security headers in `netlify.toml` only work on Netlify, not in this preview.

## Credits

The Arvo typeface is by Anton Koovit, used under the SIL Open Font License
(`fonts/OFL.txt`).
