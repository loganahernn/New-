# The Denture Clinic — website

A static marketing site for a denture practice: seven pages of plain HTML, one
stylesheet, one small JavaScript file. No build step, no dependencies, no
third-party requests.

> **Not ready to publish.** Every business-specific detail — phone number,
> address, prices, testimonials, GDC numbers — is a placeholder. See
> [`PLACEHOLDERS.md`](PLACEHOLDERS.md) before this goes anywhere near a live
> domain.

## Pages

| File | Purpose |
| --- | --- |
| `index.html` | Home — hero, treatments overview, process, testimonials |
| `treatments.html` | Full detail and guide prices for each treatment |
| `about.html` | The practice, what a clinical dental technician is, the team |
| `faqs.html` | Eleven common questions, as a native `<details>` accordion |
| `contact.html` | Enquiry form, address, opening hours, complaints procedure |
| `privacy.html` | Privacy notice (skeleton — needs completing) |
| `accessibility.html` | Accessibility statement |
| `404.html` | Not-found page (uses root-relative links, so it works from any depth) |

Plus `robots.txt` and `sitemap.xml`.

## Running it locally

There is nothing to install. Open `index.html` in a browser, or serve the folder
so root-relative links and the 404 page behave as they will in production:

```sh
python3 -m http.server 8000
# then visit http://localhost:8000
```

## Deploying

Any static host works. The repository root *is* the site root.

**GitHub Pages** — Settings → Pages → Deploy from branch → `main` / `/ (root)`.
`404.html` is picked up automatically.

**Netlify / Cloudflare Pages / Vercel** — connect the repo, leave the build
command empty, set the publish directory to `/`.

Whichever you choose, update the canonical URLs, `sitemap.xml` and `robots.txt`
if the domain differs (item 9 in `PLACEHOLDERS.md`).

## How it is put together

```
├── index.html, treatments.html, about.html, faqs.html,
│   contact.html, privacy.html, accessibility.html, 404.html
├── assets/
│   ├── css/styles.css      single stylesheet, ~22 commented sections
│   └── js/main.js          nav toggle, sticky header, form handling
├── robots.txt
├── sitemap.xml
└── PLACEHOLDERS.md         what to replace before launch
```

**Design tokens.** Colours, type scale, spacing, radii and shadows are CSS custom
properties at the top of `styles.css`. Rebranding is mostly a matter of changing
the `--brand-*` values — but re-check contrast afterwards, since the palette was
chosen to clear WCAG AA.

**No templating.** The header and footer are duplicated in each page. That is the
cost of having no build step: a change to the navigation means editing every
file. With seven pages it is manageable, and `sed` handles the mechanical cases:

```sh
sed -i 's/OLD PHONE/NEW PHONE/g' *.html
```

If the site grows past a dozen pages, that trade stops paying — move to Astro or
Eleventy at that point.

**Progressive enhancement.** Every page works with JavaScript disabled. The mobile
navigation is visible in the markup and only collapses once the toggle script has
run, so a failed script leaves the menu open rather than unreachable.

**Accessibility.** Skip link, visible focus outlines, semantic landmarks, ordered
headings, labelled form fields with `role="alert"` error slots, AA contrast, and
a `prefers-reduced-motion` block that disables smooth scrolling and transitions.

**Contact form.** No backend. Set `data-endpoint` on the form to POST enquiries as
JSON to any handler you like; leave it empty and it falls back to opening the
visitor's mail client with the message pre-filled. Details in `PLACEHOLDERS.md`.

## Content

All copy on the site was written from scratch for this build. The general dental
information in the FAQs and treatment descriptions is written to be accurate but
is not clinical advice — have a registered clinician review it before publishing,
particularly anything about timescales, aftercare and what direct access allows.
