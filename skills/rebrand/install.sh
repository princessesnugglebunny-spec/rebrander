#!/usr/bin/env bash
# Install the rebrander agent + skill globally for OpenCode (and mirror to Claude Code).
#
# Usage:
#   bash install.sh [SOURCE_ROOT]
#   REBRANDER_HOME=/path/to/dist bash install.sh
#
# SOURCE_ROOT should contain agents/rebrander.md and skills/rebrand/.
# If omitted, the script looks in a few common locations.
set -euo pipefail

OPENCODE_CONFIG="${HOME}/.config/opencode"
CLAUDE_SKILLS="${HOME}/.claude/skills"

# Resolve source root.
if [ -n "${1:-}" ]; then SRC_ROOT="$1"
elif [ -n "${REBRANDER_HOME:-}" ]; then SRC_ROOT="$REBRANDER_HOME"
else
  for c in "$HOME/rebrander" "$HOME/src/rebrander" "$(dirname "$0")/.." "$(dirname "$0")"; do
    if [ -f "$c/agents/rebrander.md" ] || [ -f "$c/rebrander.md" ]; then SRC_ROOT="$c"; break; fi
  done
fi

if [ -z "${SRC_ROOT:-}" ] || [ ! -d "$SRC_ROOT" ]; then
  echo "Could not locate source root. Pass it as the first argument or set REBRANDER_HOME."
  exit 1
fi

echo "Installing from ${SRC_ROOT} into ${OPENCODE_CONFIG} ..."
mkdir -p "${OPENCODE_CONFIG}/agents" "${OPENCODE_CONFIG}/skills"

# Agent file.
if [ -f "${SRC_ROOT}/agents/rebrander.md" ]; then
  cp "${SRC_ROOT}/agents/rebrander.md" "${OPENCODE_CONFIG}/agents/rebrander.md"
elif [ -f "${SRC_ROOT}/rebrander.md" ]; then
  cp "${SRC_ROOT}/rebrander.md" "${OPENCODE_CONFIG}/agents/rebrander.md"
else
  echo "  WARNING: rebrander.md not found; skipping agent install."
fi

# Skill dir.
SKILL_SRC=""
for c in "${SRC_ROOT}/skills/rebrand" "${SRC_ROOT}/rebrand" "${SRC_ROOT}"; do
  if [ -f "$c/SKILL.md" ]; then SKILL_SRC="$c"; break; fi
done
if [ -z "$SKILL_SRC" ]; then
  echo "  ERROR: SKILL.md not found under ${SRC_ROOT}"; exit 1
fi
rm -rf "${OPENCODE_CONFIG}/skills/rebrand"
cp -r "${SKILL_SRC}" "${OPENCODE_CONFIG}/skills/rebrand"
rm -f "${OPENCODE_CONFIG}/skills/rebrand/install.sh" "${OPENCODE_CONFIG}/skills/rebrand/index.json"

# Mirror to Claude Code (OpenCode also discovers ~/.claude/skills).
mkdir -p "${CLAUDE_SKILLS}"
rm -rf "${CLAUDE_SKILLS}/rebrand"
cp -r "${OPENCODE_CONFIG}/skills/rebrand" "${CLAUDE_SKILLS}/rebrand"

echo "Done. Restart OpenCode (or run 'opencode reload') to pick up the agent + skill."
echo "Verify: opencode debug agents | grep rebrander"
