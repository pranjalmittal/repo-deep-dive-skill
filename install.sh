#!/usr/bin/env bash
# Install the repo-deep-dive Agent Skill into a coding agent's skill directory.
#
# Usage:
#   ./install.sh [--agent AGENT] [--scope personal|project] [--dir PATH]
#
# Examples:
#   ./install.sh
#   ./install.sh --agent codex --scope project
#   curl -fsSL https://raw.githubusercontent.com/pranjalmittal/repo-deep-dive/main/install.sh | bash

set -euo pipefail

REPO_URL="https://github.com/pranjalmittal/repo-deep-dive.git"
SKILL_NAME="repo-deep-dive"

agent="claude"
scope="personal"
target=""

usage() {
    cat <<EOF
Usage: $0 [--agent AGENT] [--scope personal|project] [--dir PATH]

Agents: claude (default), codex, cursor, copilot
Scopes: personal (default), project

--dir PATH  Install into PATH instead of the agent/scope default.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --agent) agent="$2"; shift 2 ;;
        --scope) scope="$2"; shift 2 ;;
        --dir) target="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
    esac
done

if [[ -z "$target" ]]; then
    case "$agent" in
        claude)
            base_personal="$HOME/.claude/skills"
            base_project=".claude/skills"
            ;;
        codex)
            base_personal="$HOME/.codex/skills"
            base_project=".agents/skills"
            ;;
        cursor)
            base_personal="$HOME/.cursor/skills"
            base_project=".cursor/skills"
            ;;
        copilot)
            base_personal="$HOME/.copilot/skills"
            base_project=".github/skills"
            ;;
        *)
            echo "Unknown agent: $agent" >&2
            exit 2
            ;;
    esac

    if [[ "$scope" == "personal" ]]; then
        base="$base_personal"
    elif [[ "$scope" == "project" ]]; then
        base="$base_project"
    else
        echo "Unknown scope: $scope" >&2
        exit 2
    fi

    target="$base/$SKILL_NAME"
fi

mkdir -p "$(dirname "$target")"

if [[ -d "$target/.git" ]]; then
    echo "Updating existing installation at $target"
    git -C "$target" pull --ff-only
else
    echo "Installing $SKILL_NAME to $target"
    git clone "$REPO_URL" "$target"
fi

echo "Installed: $target"
echo "Invoke the skill as: $SKILL_NAME"
