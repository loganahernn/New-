#!/usr/bin/env bash
# Double-click this file in Finder to set up and run tt-autoapply.
#
# macOS opens .command files in Terminal automatically, so there's nothing to
# type. Installs anything missing, then runs the guided setup.

cd "$(dirname "$0")" || exit 1

if [ ! -x .venv/bin/tt-autoapply ]; then
    echo "First run - installing. This takes a couple of minutes."
    bash setup.sh || {
        echo
        echo "Setup failed. Copy the error above and send it over."
        read -r -p "Press Enter to close... "
        exit 1
    }
fi

./.venv/bin/tt-autoapply start

echo
read -r -p "Press Enter to close this window... "
