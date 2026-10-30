#!/usr/bin/env bash
# Install the repo-deep-dive Agent Skill for a common agent or into a chosen directory.
#
# Usage:
#   ./install.sh [--agent AGENT] [--scope personal|project] [--dir PATH] [--ref REF] [--link]
#
# Examples:
#   ./install.sh
#   ./install.sh --agent codex
#   ./install.sh --agent my-agent
#   ./install.sh --ref v0.1.0
#   ./install.sh --dir /path/to/agent/skills/repo-deep-dive --link

set -euo pipefail

REPO_URL="https://github.com/pranjalmittal/repo-deep-dive-skill.git"
SKILL_NAME="repo-deep-dive"
DEFAULT_REF="main"

agent=""
scope="personal"
target=""
ref="$DEFAULT_REF"
link_from_checkout=false

usage() {
    cat <<EOF
Usage: $0 [--agent AGENT] [--scope personal|project] [--dir PATH] [--ref REF] [--link]

Common agents: codex, claude, cursor, copilot
--agent AGENT  Install for a common agent, or enter a custom agent name.
--scope SCOPE  Use the agent's personal or project skill directory (default: personal).
--dir PATH     Install into this skill directory, bypassing agent path selection.
--ref REF      Git tag, branch, or commit to install (default: $DEFAULT_REF).
--link         Symlink this local checkout instead of cloning from GitHub.
               Requires running install.sh from a checkout.

Run with --help to see this message.
EOF
}

fail() {
    echo "Error: $*" >&2
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --agent)
            (($# >= 2)) || fail "--agent requires a value"
            [[ "$2" != --* ]] || fail "--agent requires a value"
            agent="$2"
            shift 2
            ;;
        --scope)
            (($# >= 2)) || fail "--scope requires a value"
            [[ "$2" != --* ]] || fail "--scope requires a value"
            scope="$2"
            shift 2
            ;;
        --dir)
            (($# >= 2)) || fail "--dir requires a value"
            [[ "$2" != --* ]] || fail "--dir requires a value"
            target="$2"
            shift 2
            ;;
        --ref)
            (($# >= 2)) || fail "--ref requires a value"
            [[ "$2" != --* ]] || fail "--ref requires a value"
            ref="$2"
            shift 2
            ;;
        --link)
            link_from_checkout=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 2
            ;;
    esac
done

if [[ -z "$target" && -z "$agent" ]]; then
    if [[ -t 0 ]]; then
        cat <<EOF
Choose an agent:
  1) Codex
  2) Claude Code
  3) Cursor
  4) GitHub Copilot
  5) Other
EOF
        read -r -p "Selection [1-5]: " selection
        case "$selection" in
            1) agent="codex" ;;
            2) agent="claude" ;;
            3) agent="cursor" ;;
            4) agent="copilot" ;;
            5) agent="other" ;;
            *) fail "choose a number from 1 to 5" ;;
        esac
    else
        fail "specify --agent AGENT or --dir PATH"
    fi
fi

if [[ -z "$target" ]]; then
    case "$agent" in
        codex)
            base_personal="${CODEX_HOME:-$HOME/.codex}/skills"
            base_project=".agents/skills"
            ;;
        claude|claude-code)
            base_personal="$HOME/.claude/skills"
            base_project=".claude/skills"
            ;;
        cursor)
            base_personal="$HOME/.cursor/skills"
            base_project=".cursor/skills"
            ;;
        copilot|github-copilot)
            base_personal="$HOME/.copilot/skills"
            base_project=".github/skills"
            ;;
        *)
            if [[ -t 0 ]]; then
                read -r -p "Enter the skill directory path for '$agent': " target
            else
                fail "no built-in path for '$agent'; pass --dir PATH"
            fi
            [[ -n "$target" ]] || fail "enter a skill directory path or pass --dir PATH"
            ;;
    esac

    if [[ -z "$target" ]]; then
        if [[ "$scope" == "personal" ]]; then
            target="$base_personal/$SKILL_NAME"
        elif [[ "$scope" == "project" ]]; then
            project_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)"
            target="$project_root/$base_project/$SKILL_NAME"
        else
            fail "unknown scope '$scope'; choose personal or project"
        fi
    fi
fi

mkdir -p "$(dirname "$target")"
target_parent="$(cd "$(dirname "$target")" && pwd -P)"
target="$target_parent/$(basename "$target")"

checkout_dir=""
script_path="${BASH_SOURCE[0]:-}"
if [[ -n "$script_path" && -f "$script_path" ]]; then
    checkout_dir="$(cd "$(dirname "$script_path")" && pwd -P)"
fi

if [[ "$link_from_checkout" == true ]]; then
    [[ -n "$checkout_dir" ]] ||
        fail "--link requires running install.sh from a local checkout"

    source_dir="$checkout_dir"
    [[ -f "$source_dir/SKILL.md" ]] ||
        fail "could not find SKILL.md next to install.sh"

    [[ "$target" != "$source_dir" ]] ||
        fail "install target is the source checkout itself"
    case "$target/" in
        "$source_dir/"*)
            fail "cannot symlink the checkout into one of its own subdirectories"
            ;;
    esac

    if [[ -L "$target" ]]; then
        if [[ -d "$target" ]] && [[ "$(cd -- "$target" && pwd -P)" == "$source_dir" ]]; then
            echo "Already linked: $target -> $source_dir"
            exit 0
        fi
        fail "target is an existing symlink: $target"
    fi
    [[ ! -e "$target" ]] || fail "target already exists: $target"

    ln -s "$source_dir" "$target"
    echo "Linked $SKILL_NAME to $target"
    echo "Source checkout: $source_dir"
else
    if [[ -L "$target" ]]; then
        if [[ -n "$checkout_dir" && -d "$target" ]] &&
            [[ "$(cd -- "$target" && pwd -P)" == "$checkout_dir" ]]; then
            echo "Already linked: $target -> $checkout_dir"
            exit 0
        fi
        fail "target is a symlink: $target; use --link for a local checkout or choose another path"
    elif [[ -e "$target" ]]; then
        git -C "$target" rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
            fail "target exists and is not a Git checkout: $target"

        origin="$(git -C "$target" remote get-url origin 2>/dev/null || true)"
        normalized_origin="${origin%.git}"
        case "$normalized_origin" in
            https://github.com/pranjalmittal/repo-deep-dive-skill|\
            git@github.com:pranjalmittal/repo-deep-dive-skill|\
            ssh://git@github.com/pranjalmittal/repo-deep-dive-skill)
                ;;
            *)
                fail "target is not a checkout of $REPO_URL: $target"
                ;;
        esac

        echo "Updating existing installation at $target"
        git -C "$target" fetch --tags --prune
        git -C "$target" checkout --quiet "$ref" ||
            fail "could not check out '$ref' in $target"
        if git -C "$target" symbolic-ref -q HEAD >/dev/null; then
            git -C "$target" pull --ff-only
        else
            echo "Checked out $ref (detached HEAD)"
        fi
    else
        echo "Installing $SKILL_NAME at $ref to $target"
        git clone "$REPO_URL" "$target"
        git -C "$target" checkout --quiet "$ref" ||
            fail "could not check out '$ref' in $target"
    fi

    [[ -f "$target/SKILL.md" ]] || fail "installed checkout has no SKILL.md: $target"
fi

echo "Invoke the skill as: $SKILL_NAME"
