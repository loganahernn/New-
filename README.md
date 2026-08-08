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
properties at the top of `styles.css`. Colours are OKLCH, which is perceptually
uniform — stepping the lightness channel gives an even ramp instead of the lumpy
one hex produces. Rebranding is mostly a matter of changing the `--teal-*` ramp
and the semantic tokens built on it, but re-check contrast afterwards: both
themes were measured against WCAG AA, not eyeballed.

**Cascade layers.** The stylesheet declares `@layer reset, base, layout,
components, utilities`. A later layer beats an earlier one no matter how
specific the selector, which removes a whole category of specificity bug — an
earlier version of this site had an unreadable header button because a layout
rule outranked the component that styled it.

**Light and dark.** Every semantic token is a `light-dark()` pair, so the entire
theme flips from the single `color-scheme` declaration on `:root`. The site
follows the operating system by default; the header button overrides it and
stores the choice. A tiny inline script in each `<head>` applies a stored choice
before first paint, so there is no flash of the wrong theme.

**Modern layout.** Container queries let cards adapt to the width of their own
column rather than the viewport. Cross-document view transitions animate between
pages where supported. Speculation rules prerender same-origin links on hover, so
navigation feels instant. All three degrade silently to ordinary behaviour.

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
headings, labelled form fields with `role="alert"` error slots, AA contrast in
both themes, and a `prefers-reduced-motion` block that disables smooth scrolling,
transitions and view transitions.

**Contact form.** No backend. Set `data-endpoint` on the form to POST enquiries as
JSON to any handler you like; leave it empty and it falls back to opening the
visitor's mail client with the message pre-filled. Details in `PLACEHOLDERS.md`.

## Content

All copy on the site was written from scratch for this build.

Two points are load-bearing and were checked against current guidance rather
than written from memory:

- **Direct access.** A clinical dental technician may treat a patient directly
  only where the patient has no natural teeth and no implants, for the provision
  and maintenance of full dentures. Any patient who is dentate, or who has
  implants, must be treated on a *prescription* from a dentist — repairs and
  shade-taking being the exceptions. The site states this in three places
  (`about.html`, `faqs.html`, `treatments.html`); keep them consistent if you
  edit one.
- **Record retention** (`privacy.html`). Guidance is not uniform — NHS advice for
  England and Wales gives 15 years for an adult, while 11 years is the commonly
  cited professional figure. The page asks you to state your own policy rather
  than repeat a range.

The rest of the dental information is written to be accurate but is not clinical
advice. Have a registered clinician review it before publishing, particularly
timescales and aftercare.
