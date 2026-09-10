#!/usr/bin/env bash
# Symlink the resume-tailoring skill into every local harness that reads
# agentskills.io-format SKILL.md files. Idempotent; symlinks, never copies.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

link() { # name target_dir
  local name="$1" dir="$2"
  mkdir -p "$dir"
  if [ -L "$dir/$name" ] || [ -e "$dir/$name" ]; then
    if [ "$(readlink "$dir/$name" 2>/dev/null)" = "$REPO" ]; then return 0; fi
    echo "skip $dir/$name (exists, not managed by this script)" >&2
    return 0
  fi
  ln -s "$REPO" "$dir/$name"
  echo "linked $dir/$name -> $REPO"
}

link resume-tailoring "$HOME/.pi/agent/skills"
link resume-tailoring "$HOME/.claude/skills" 2>/dev/null || true
link resume-tailoring "$HOME/.agents/skills"

# Hermes: plugin-style directory with a skills/ subdirectory
mkdir -p "$HOME/.hermes/plugins/resume-tailoring/skills"
if [ ! -e "$HOME/.hermes/plugins/resume-tailoring/skills/resume-tailoring" ]; then
  ln -s "$REPO" "$HOME/.hermes/plugins/resume-tailoring/skills/resume-tailoring"
  echo "linked ~/.hermes/plugins/resume-tailoring/skills/resume-tailoring -> $REPO"
fi

echo "done - restart each harness so its skill catalog picks it up"
