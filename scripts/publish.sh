#!/usr/bin/env bash
# Copies the skill into a checkout of the public nemira-labs/skills, which `npx skills add` installs
# from. It changes that checkout's files and stops: look at the diff, then commit and push there
# yourself.
#
#   scripts/publish.sh ../skills
set -euo pipefail
cd "$(dirname "$0")/.."

target=${1:?"usage: scripts/publish.sh <checkout of nemira-labs/skills>"}
if [ ! -d "$target/.git" ] || [ ! -d "$target/skills" ]; then
  echo "$target isn't a checkout of nemira-labs/skills" >&2
  exit 1
fi

scripts/check.sh

rm -rf "$target/skills/unfold"
mkdir -p "$target/skills/unfold"
cp -R skills/unfold/. "$target/skills/unfold/"
chmod +x "$target/skills/unfold/scripts/unfold"

version=$(sed -n 's/^  version: "\(.*\)"$/\1/p' skills/unfold/SKILL.md)
echo
echo "skills/unfold $version copied to $target. Its README lists the skills: add unfold there if it"
echo "isn't listed. Then review and publish:"
git -C "$target" status --short
