# The Denture Clinic — website

A static marketing site for a denture practice: eight pages of plain HTML, one
stylesheet, one small JavaScript file and a set of original SVG illustrations.
No build step, no dependencies, no third-party requests.

Designed for an older audience — large type, large targets, black on white, and
a phone number that is never more than a glance away.

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
│   ├── css/styles.css      single stylesheet, layered and commented
│   ├── js/main.js          nav toggle, sticky header, print, form handling
│   └── img/*.svg           seven original illustrations
├── robots.txt
├── sitemap.xml
└── PLACEHOLDERS.md         what to replace before launch
```

**Built for an older audience.** That is the constraint everything else follows
from:

- Body text starts at 19px and scales up, never down. Nothing on the site is
  below 18px.
- Every button, link and form control is at least 56px tall — more than double
  the 24px WCAG 2.2 minimum. Small targets are the biggest single obstacle for
  anyone with less steady hands or poorer close vision.
- Black on white throughout: a contrast ratio of 21:1.
- Links inside paragraphs stay underlined, so they are never identified by
  colour alone.
- The phone number sits in the header on desktop and in a large call band on
  every page. It is the action most of these visitors actually want, so the
  "Book a consultation" button is hidden on desktop rather than competing with
  it — it still appears in the mobile menu.
- One theme, no dark mode, no theme switch: one fewer control to understand.

**Design tokens.** Colour, type scale, spacing, radii and targets are CSS custom
properties at the top of `styles.css`. The palette is white, black, and a light
purple (`--purple: #c9a9f0`) used for buttons and highlights, with a deeper
purple (`--purple-deep: #5b2e96`) for links and focus rings. Both were measured,
not eyeballed: black on the button purple is 10.4:1, and the link purple on
white is 9.2:1.

**Cascade layers.** The stylesheet declares `@layer reset, base, layout,
components, utilities`. A later layer beats an earlier one no matter how
specific the selector, which removes a whole category of specificity bug.

**Illustrations.** `assets/img/` holds seven SVG illustrations drawn from
scratch for this site — a full denture, a partial with clasps, an
implant-retained denture, an immediate denture, a repair, a mouthguard, and a
larger hero version. They are original artwork, so there is no licence,
attribution or expiry to track. Being SVG they stay sharp at any size and add
about 3KB each. Swap them for real photographs whenever you have them.

**Modern layout.** Container queries let cards adapt to their own column width
rather than the viewport. Cross-document view transitions animate between pages
where supported, and speculation rules prerender same-origin links on hover.
All degrade silently.

**No templating.** The header and footer are duplicated in each page. That is the
cost of having no build step: a change to the navigation means editing every
file. With eight pages it is manageable, and `sed` handles the mechanical cases:

```sh
sed -i 's/OLD PHONE/NEW PHONE/g' *.html
```

If the site grows past a dozen pages, that trade stops paying — move to Astro or
Eleventy at that point.

**Progressive enhancement.** Every page works with JavaScript disabled. The mobile
navigation is visible in the markup and only collapses once the toggle script has
run, so a failed script leaves the menu open rather than unreachable.

**Accessibility.** Skip link, thick visible focus outlines, semantic landmarks,
ordered headings, labelled form fields with `role="alert"` error slots, 21:1 body
contrast, 56px minimum targets, and a `prefers-reduced-motion` block that
disables smooth scrolling, transitions and view transitions.

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
