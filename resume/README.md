# Resume site

A small, dependency-free single-page resume built with plain HTML, CSS, and JS.

## Run it

No build step. Just open `resume/index.html` in a browser, or serve the folder:

```bash
# from the repo root
python3 -m http.server 8080 --directory resume
# then visit http://localhost:8080
```

## Customize

Everything that's likely to change is in `index.html`:

- **Header / hero** — name, title, lede, contact links.
- **Experience** — `<li class="timeline-item">` blocks under `#experience`.
- **Projects** — `<article class="card">` blocks under `#projects`.
- **Skills** — the `dt`/`dd` pairs in `.skill-grid`.
- **Education** — `.edu-list`.
- **Contact** — `.contact-list`.

Drop a `resume.pdf` next to `index.html` to make the "Download PDF" button work,
or remove the link if you'd rather only offer the print-to-PDF flow.

## Theming

Colors live as CSS custom properties at the top of `styles.css`:

- `:root { ... }` — light mode.
- `[data-theme="dark"] { ... }` — dark mode.

The toggle in the top-right persists the chosen mode in `localStorage` and
otherwise follows the OS preference.

## Print / PDF

The print stylesheet at the bottom of `styles.css` hides chrome (top bar,
footer, buttons) and tightens spacing, so `Cmd/Ctrl + P` → "Save as PDF"
produces a clean one- or two-page resume.

## Deploy

Any static host works — GitHub Pages, Netlify, Vercel, Cloudflare Pages,
S3+CloudFront. Point the host at the `resume/` directory.
