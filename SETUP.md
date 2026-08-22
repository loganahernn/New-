# Setup, step by step

No programming needed. You copy a line, paste it, press Enter. About 10 minutes,
most of it waiting for downloads.

---

## Step 1 — Open a terminal

**Mac:** press `Cmd + Space`, type `terminal`, press Enter. A white or black
window with text opens. That's it.

**Windows:** press the Start button, type `powershell`, press Enter.

It looks intimidating. It's just a place to type commands instead of clicking
buttons. You can't break anything by typing the lines below.

---

## Step 2 — Get the code onto your computer

Copy and paste this whole block, then press Enter:

**Mac:**
```bash
cd ~/Desktop
git clone https://github.com/loganahernn/New-.git talent-talks
cd talent-talks
git checkout claude/talent-talks-auto-apply-g7rj81
```

**Windows:**
```powershell
cd ~\Desktop
git clone https://github.com/loganahernn/New-.git talent-talks
cd talent-talks
git checkout claude/talent-talks-auto-apply-g7rj81
```

That puts a folder called `talent-talks` on your Desktop.

> **"git: command not found"?** On Mac, run `xcode-select --install` and accept
> the prompt, then try again. On Windows, install Git from
> [git-scm.com/download/win](https://git-scm.com/download/win), then close and
> reopen PowerShell.

---

## Step 3 — Run the setup script

**Mac:**
```bash
bash setup.sh
```

**Windows:**
```powershell
.\setup.bat
```

This installs everything and takes a minute or two. When it finishes it prints
"Done" and tells you what's next. Re-running it later is safe — it won't
overwrite anything you've edited.

> **"Python 3.10 or newer is needed"?** Install it from
> [python.org/downloads](https://www.python.org/downloads/) — on Windows, tick
> **Add Python to PATH** in the installer — then run the setup line again.

---

## Step 4 — Log in

```bash
./.venv/bin/tt-autoapply login
```

*(Windows: `.venv\Scripts\tt-autoapply login`)*

A browser window opens. Sign in to Talent Talks exactly as you normally would,
click through to the auditions page, then come back to the terminal and press
Enter.

Your password goes into the real Talent Talks login page and nowhere else — the
tool never sees it. It only keeps the "you're signed in" cookie afterwards.

---

## Step 5 — Read the page structure

```bash
./.venv/bin/tt-autoapply discover
```

*(Windows: `.venv\Scripts\tt-autoapply discover`)*

This is the step that teaches the tool what a Talent Talks listing looks like.
It doesn't apply to anything or change anything — it just looks and reports.

It prints something like:

```
Repeated blocks (likely listing cards) — paste one into selectors.listing_item:

  div.audition-card   x18
    headings: h3.card-title
    link: 'Male Lead Wanted' -> /auditions/male-lead-wanted/
    text: London · Paid · Posted 2 days ago
```

**Copy everything it printed and send it back to me.** I'll fill in
`config.yaml` for you and you won't have to touch it.

It also saves the same thing to `state/discover/listing-report.json` — if the
terminal output is awkward to copy, send me that file instead.

Then do the same for one individual role page, so the application form gets
mapped too. Open any audition on the site, copy its address from the browser,
and run:

```bash
./.venv/bin/tt-autoapply discover --url https://www.talenttalks.co.uk/auditions/whatever-role/
```

Send me that output as well.

### If it says it found nothing

Two usual causes:

- **Not logged in.** Run step 4 again.
- **The page loads its listings a moment after opening.** Run it with
  `--headed` so you can watch what the browser actually sees:
  ```bash
  ./.venv/bin/tt-autoapply discover --headed
  ```

Either way, `state/discover/listing.png` is a screenshot of exactly what the
tool saw. Send me that and I'll tell you what's going on.

---

## Step 6 — Your profile

Once your config is filled in, pull your details straight off your Talent Talks
profile instead of typing them:

```bash
./.venv/bin/tt-autoapply import-profile --url https://www.talenttalks.co.uk/your-profile-page
```

Then fill in anything it missed without opening a file:

```bash
./.venv/bin/tt-autoapply set --name "Your Name" --email you@example.com --phone "07700 900000"
```

Run `set` with no options to see what's filled in and what's still blank.

---

## Step 7 — Check before going live

```bash
./.venv/bin/tt-autoapply scan
```

This applies to **nothing**. It shows you what it would do and why:

```
  [FIT 0.85] playing age 18-25 overlaps yours; casting male; London   Male Lead - TV Commercial
  [SKIP 0.50] casting female, you are male                            Female Lead - Feature
  [SKIP 0.50] unpaid / expenses only                                  Graduate Short
```

Read down that list. If the FITs are roles you'd genuinely go for and the SKIPs
are ones you wouldn't, it's working. If not, send me the output and I'll adjust
the filters.

Next step up — fills in the forms and screenshots them, still submits nothing:

```bash
./.venv/bin/tt-autoapply run
```

The screenshots land in `state/screenshots/`. Open a couple and check you're
happy with what would be sent.

---

## Step 8 — Go live

Only when steps 5–7 look right:

```bash
./.venv/bin/tt-autoapply run --apply
```

The first time you run this it will apply to **nothing** — it records what's
already on the board so you don't fire off applications to briefs that closed
weeks ago. From then on it goes for new posts only.

To have it keep checking every hour:

```bash
./.venv/bin/tt-autoapply watch --interval 60 --apply
```

Leave that terminal window open. `Ctrl + C` stops it.

To see what it's applied to:

```bash
./.venv/bin/tt-autoapply history
```

---

## If something goes wrong

Copy the error and send it over. Nothing here can damage your computer or your
Talent Talks account — the worst case is a command refuses to run.

The one thing worth being careful about: `--apply` is the only flag that
submits anything. Without it, everything is a rehearsal.
