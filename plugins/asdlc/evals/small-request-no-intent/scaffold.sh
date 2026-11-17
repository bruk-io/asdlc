#!/bin/sh
# The same repository as the acting case, with a typo for the request to fix.
set -eu
git init --quiet -b main .
git config user.name "Dana Okafor"
git config user.email dana.okafor@example.com
printf '# Claims portal\n\nThe portal ajdusters use to work a claim.\n' >README.md
git add README.md
git commit --quiet -m "Start"
