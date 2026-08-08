# Placeholders to replace before publishing

Nothing on this site was copied from the existing thedentureclinic.org.uk — that
domain is blocked from the build environment, so **every** business-specific
detail below is invented and must be replaced with real information.

Work through this list top to bottom. Anything marked **must** is either a legal
requirement or something that would actively mislead patients if left as-is.

---

## 1. Contact details

The phone number is now **real**: `01582 462880`, taken from your existing site
and used across every page, the call bar, the footer and the JSON-LD.

Still to replace:

| Placeholder | Where | Replace with |
| --- | --- | --- |
| `reception@example.com` | every page footer, `contact.html`, `accessibility.html`, form `data-mailto` | Real address. |
| `1 Example Street, Townville, AB1 2CD` | every page footer, `contact.html` | Real address. |
| Opening hours table | `contact.html` | Real hours. Also update the JSON-LD in `index.html`. |
| "Getting here" text | `contact.html` | Parking, transport, step-free access. |

Quick check that you got them all:

```sh
grep -rn "example.com\|Example Street\|Townville\|AB1 2CD" .
```

## 2. Prices — **must**

`treatments.html` shows `£000` / `£00` throughout, with an amber warning box at
the top of the page.

Replace every figure with your real fees, then **delete the `<div class="notice">`
block** (search for `REMOVE THIS NOTICE BEFORE PUBLISHING`).

## 3. Testimonials — **must**

`index.html` has three placeholder reviews attributed to "A./B./C. Placeholder".

Replace them with genuine feedback you have permission to publish, or delete the
whole `<section>`. Inventing patient reviews for a healthcare practice breaches
CAP/ASA rules and consumer protection law — the placeholder text is deliberately
obvious so it cannot be published by accident.

## 4. Registration details — **must**

`about.html` carries `Registrant name — GDC no. 000000` in two places (the
"Registration and standards" panel and the three team cards).

GDC registrants must display their name and registration number. Replace the
placeholders with the real ones, and rewrite or delete the placeholder
biographies.

## 5. Privacy notice — **must**

`privacy.html` is a skeleton with `[bracketed]` gaps, not a finished notice. A
dental practice processes special-category health data, so this needs completing
and reviewing by someone qualified. Fill in:

- registered name, address, ICO registration number, privacy contact
- what you collect, and who you share it with (named processors)
- retention periods
- whether any data leaves the UK

Also delete the amber template warning at the top once it is done.

## 6. Accessibility statement

`accessibility.html` has `[bracketed]` gaps for known limitations, physical
access to the building, and a last-reviewed date. The technical claims it makes
about the site itself are accurate as built — but they stop being accurate the
moment you add a third-party widget, so re-check after any change.

## 7. Placeholder answers in the FAQs

Two answers in `faqs.html` are stubs:

- **"Do you take NHS patients?"** — one of the first things patients look for.
- **"Is the practice accessible?"**

## 8. Statistics on the home page

`index.html` shows `00` years and `0,000` dentures fitted. Use figures you can
evidence, or delete the `<dl class="stat-grid">` block.

## 9. Domain and metadata

If the site will live somewhere other than `https://www.thedentureclinic.org.uk/`:

- `<link rel="canonical">` and `og:url` in the `<head>` of every page
- `sitemap.xml` — all five `<loc>` values and the `<lastmod>` dates
- `robots.txt` — the `Sitemap:` line
- the JSON-LD block in `index.html`

## 10. Contact form endpoint

The form in `contact.html` is configured by two attributes:

```html
<form data-enquiry-form data-endpoint="" data-mailto="reception@example.com">
```

- **`data-endpoint` empty** (current state) — the form validates, then opens the
  visitor's email client with the enquiry pre-filled. It works with no backend,
  but the visitor has to press send themselves, and it fails for anyone using
  webmail without a registered mail handler.
- **`data-endpoint` set** — the form POSTs JSON to that URL. Any service that
  accepts a JSON body works: Formspree, Basin, Netlify Forms, or your own
  handler.

Set a real endpoint before launch. A honeypot field catches basic bots; add the
provider's own spam filtering as well.

Your current site uses reCAPTCHA. This rebuild deliberately does not: it would be
the only third-party request on the site, it sets cookies that need consent under
PECR, and "click the traffic lights" puzzles are exactly the sort of thing that
defeats an older visitor. The honeypot plus your form provider's own filtering is
usually enough for a practice this size. If the spam volume proves otherwise, add
it — and add a consent banner at the same time.

Because enquiries may contain health information, check your provider stores
submissions in the UK/EEA or has an adequate transfer route, and cover it in the
privacy notice.

## 11. Regulatory wording — check before you edit it

Two claims on the site were checked against current guidance rather than written
from memory. If you reword them, keep them accurate:

- **Direct access** appears in `about.html`, `faqs.html` and twice in
  `treatments.html`. A CDT may treat directly only where the patient has no
  natural teeth and no implants, for full dentures; anyone dentate or with
  implants needs a dentist's *prescription*, with repairs and shade-taking as
  the exceptions. Getting this wrong on a live site is a regulatory problem,
  not just an editorial one.
- **Record retention** in `privacy.html` — state your own policy, do not
  publish the range the template quotes.

## 12. Favicon and logo

The tooth mark is an inline SVG in the page markup and in the `<link rel="icon">`
data URI — a purple rounded square with a white tooth. Swap it for real branding
if you have it.

## 13. Illustrations and photography

`assets/img/` contains seven SVG illustrations drawn specifically for this site.
They are original artwork: no licence to comply with, no attribution required,
nothing that can be withdrawn later.

They are deliberately a stand-in for the real thing. Photographs of the practice,
the laboratory and the team would lift this site more than any other single
change, and for an older audience seeing the actual room and the actual faces
does more for confidence than any illustration.

When you swap them in:

- Keep the `width` and `height` attributes accurate to the file, so the layout
  does not jump while the image loads.
- Keep `loading="lazy"` on anything below the fold; the hero should stay eager.
- Leave `alt=""` where the adjacent heading already names the subject — a photo
  of a real person or the premises should get a real description instead.
- If you buy stock photography, keep the licence on file. If you use a free
  source, check the specific licence for that image rather than trusting the
  site as a whole.

---

## Final pre-launch checklist

- [ ] Grep for leftovers: `grep -rn "TODO\|Placeholder\|placeholder\|\[date\]" --include="*.html" .`
- [ ] Both amber `notice` blocks deleted (`treatments.html`, `privacy.html`)
- [ ] All `£000` figures replaced
- [ ] Test the contact form end to end and confirm the enquiry arrives
- [ ] Check every page at 320px wide and at 200% zoom
- [ ] Tab through each page — focus must stay visible and never get trapped
- [ ] Check both light and dark themes — the toggle is in the header
- [ ] Run Lighthouse; confirm the accessibility score and fix anything flagged
