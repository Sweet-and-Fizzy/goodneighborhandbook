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
| Colors, fonts, spacing | `css/site.css` |

Editable sections are marked with `<!-- EDIT: ... -->` comments.

## Things that are repeated in more than one file

There is no shared template, so these have to be changed everywhere they appear.

- **The menu** is in all four `.html` files.
- **The "Read the Handbook" link** (the Flipsnack address) is in the menu of all
  four files and on the home page button. If the handbook moves, search for
  `flipsnack.com` and replace every one.
- **The footer and its year** are in `index.html`, `about-us/index.html` and
  `get-a-copy/index.html`.
- **Page title and description.** The lines near the top of each page
  (`<title>`, `description`, and the `og:` lines) are what search engines and
  link previews show. Update them when the page content changes.
- **The site address** appears near the top of the three main pages, in
  `robots.txt` and in `sitemap.xml`. It only matters if the domain changes.

Adding a new page means copying an existing page folder, adding it to the menu
in all four files, and adding a line to `sitemap.xml`.

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
