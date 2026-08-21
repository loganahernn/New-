#!/usr/bin/env bash
# One-shot setup for macOS and Linux.
#
#   bash setup.sh
#
# Creates a private Python environment inside this folder, installs the tool
# and its browser, and makes your config.yaml / profile.yaml from the examples.
# Safe to re-run: it never overwrites a config or profile you've already edited.

set -euo pipefail

cd "$(dirname "$0")"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*"; }
fail() { printf '\n\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

# --- 1. Python -------------------------------------------------------------
say "1/4  Checking Python"

PYTHON=""
for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        version=$("$candidate" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "0.0")
        major=${version%%.*}
        minor=${version##*.}
        if [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python 3.10 or newer is needed but wasn't found.
Install it from https://www.python.org/downloads/ then run this script again."
fi
echo "     using $PYTHON ($($PYTHON --version))"

# --- 2. Environment --------------------------------------------------------
say "2/4  Installing tt-autoapply (this takes a minute or two)"

if [ ! -d .venv ]; then
    "$PYTHON" -m venv .venv
fi
./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet -e .

# --- 3. Browser ------------------------------------------------------------
say "3/4  Installing the browser it drives"

# Playwright needs its own Chromium build; the system browser won't do.
if ! ./.venv/bin/python -m playwright install chromium; then
    warn "Chromium install failed. Try again with:  ./.venv/bin/python -m playwright install chromium"
fi

# --- 4. Your files ---------------------------------------------------------
say "4/4  Setting up your config"

for pair in "config.example.yaml:config.yaml" "profile.example.yaml:profile.yaml"; do
    example="${pair%%:*}"
    target="${pair##*:}"
    if [ -e "$target" ]; then
        echo "     $target already exists — left alone"
    else
        cp "$example" "$target"
        echo "     created $target"
    fi
done

cat <<'DONE'

Done. Two things next:

  1. Log in (a browser window opens — sign in as you normally would):

       ./.venv/bin/tt-autoapply login

  2. Read the real page structure:

       ./.venv/bin/tt-autoapply discover

     That prints a block of text and saves a copy to
     state/discover/listing-report.json — send either one back to get your
     config.yaml filled in.

Every command starts with ./.venv/bin/tt-autoapply — there's nothing to
"activate" first.
DONE
