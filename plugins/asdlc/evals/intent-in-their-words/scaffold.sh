#!/bin/sh
# Makes the run's folder a repository `asdlc intent new` can work in: a main, one
# commit, and a name and email for the commits it makes.
set -eu
git init --quiet -b main .
git config user.name "Dana Okafor"
git config user.email dana.okafor@example.com
printf '# Claims portal\n\nThe portal adjusters use to work a claim.\n' >README.md
git add README.md
git commit --quiet -m "Start"
