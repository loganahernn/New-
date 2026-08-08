# Placeholders to replace before publishing

Nothing on this site was copied from the existing thedentureclinic.org.uk — that
domain is blocked from the build environment, so **every** business-specific
detail below is invented and must be replaced with real information.

Work through this list top to bottom. Anything marked **must** is either a legal
requirement or something that would actively mislead patients if left as-is.

---

## 1. Contact details — **must**

The same block appears in the footer of every page, plus the contact page and the
call-to-action bands.

| Placeholder | Where | Replace with |
| --- | --- | --- |
| `01632 960 001` / `tel:+441632960001` | every page footer, CTA bands, `contact.html`, `accessibility.html` | Real practice number. Keep the `tel:` link in full international form (`+44…`, no leading zero). |
| `reception@example.com` | every page footer, `contact.html`, `accessibility.html`, form `data-mailto` | Real address. |
| `1 Example Street, Townville, AB1 2CD` | every page footer, `contact.html` | Real address. |
| Opening hours table | `contact.html` | Real hours. Also update the JSON-LD in `index.html`. |
| "Getting here" text | `contact.html` | Parking, transport, step-free access. |

`01632 960 001` is an Ofcom number reserved for drama, so it can never ring a
real person — but it will look plausible to a visitor. Do not ship it.

Quick check that you got them all:

```sh
grep -rn "1632960001\|01632 960 001\|example.com\|Example Street\|Townville\|AB1 2CD" .
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

Because enquiries may contain health information, check your provider stores
submissions in the UK/EEA or has an adequate transfer route, and cover it in the
privacy notice.

## 11. Favicon and logo

The tooth mark is an inline SVG defined per page (in the `<link rel="icon">` data
URI and in the header/footer markup). Swap it for real branding if you have it.

## 12. Photography

There is no photography anywhere — the hero is an abstract SVG. Real photos of
the practice, the laboratory and the team would lift the site more than any other
single change. Add them with explicit `width`/`height` attributes and
`loading="lazy"` on anything below the fold.

---

## Final pre-launch checklist

- [ ] Grep for leftovers: `grep -rn "TODO\|Placeholder\|placeholder\|\[date\]" --include="*.html" .`
- [ ] Both amber `notice` blocks deleted (`treatments.html`, `privacy.html`)
- [ ] All `£000` figures replaced
- [ ] Test the contact form end to end and confirm the enquiry arrives
- [ ] Check every page at 320px wide and at 200% zoom
- [ ] Tab through each page — focus must stay visible and never get trapped
- [ ] Run Lighthouse; confirm the accessibility score and fix anything flagged
