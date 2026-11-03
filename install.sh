#!/usr/bin/env bash
# PDF2MD Skill Installer
# Installs the complete pdf2md Skill for Claude Code or Codex.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SKILL_NAME="pdf2md"

usage() {
    cat <<'EOF'
Usage: ./install.sh [claude|codex]

Options:
  claude    Install to ~/.claude/skills/pdf2md
  codex     Install to ~/.codex/skills/pdf2md
  -h, --help

If no agent is specified, the installer checks for Claude Code first, then Codex.
EOF
}

detect_agent() {
    if [[ -n "${CLAUDE_CODE:-}" ]] || command -v claude >/dev/null 2>&1; then
        printf '%s\n' "claude"
    elif command -v codex >/dev/null 2>&1; then
        printf '%s\n' "codex"
    else
        printf '%s\n' "unknown"
    fi
}

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

case "${1:-}" in
    -h|--help)
        usage
        exit 0
        ;;
    claude)
        agent="claude"
        ;;
    codex)
        agent="codex"
        ;;
    "")
        agent="$(detect_agent)"
        ;;
    *)
        usage >&2
        fail "Unsupported agent type: $1"
        ;;
esac

case "$agent" in
    claude)
        skills_root="$HOME/.claude/skills"
        ;;
    codex)
        skills_root="$HOME/.codex/skills"
        ;;
    unknown)
        fail "No supported agent detected. Run './install.sh [claude|codex]'."
        ;;
    *)
        fail "Unsupported agent type: $agent"
        ;;
esac

required_files=(
    "SKILL.md"
    "config.example.yaml"
    "skills/setup/SKILL.md"
    "skills/config/SKILL.md"
    "skills/run/SKILL.md"
    "skills/retry/SKILL.md"
    "references/figure_rules.md"
    "references/architecture.md"
    "references/troubleshooting.md"
    "examples/pipeline.py"
    "examples/check_failures.py"
    "examples/retry_failures.py"
    "examples/resume_step6.py"
    "examples/assemble_md.py"
    "examples/run_manifest.py"
    "examples/vlm_client.py"
)

for relative_path in "${required_files[@]}"; do
    [[ -f "$SCRIPT_DIR/$relative_path" ]] \
        || fail "Source file not found: $SCRIPT_DIR/$relative_path"
done

timestamp="$(date +%Y%m%d-%H%M%S)"
target="$skills_root/$SKILL_NAME"
stage="$skills_root/.$SKILL_NAME-install-$timestamp"
backup="$skills_root/$SKILL_NAME.backup-$timestamp"

cleanup() {
    if [[ -n "${stage:-}" && -d "$stage" ]]; then
        case "$stage" in
            "$skills_root"/."$SKILL_NAME"-install-*) rm -rf -- "$stage" ;;
        esac
    fi
}
trap cleanup EXIT

mkdir -p "$skills_root"
[[ ! -e "$stage" ]] || fail "Staging directory already exists: $stage"
[[ ! -e "$backup" ]] || fail "Backup directory already exists: $backup"

mkdir -p \
    "$stage/skills/setup" \
    "$stage/skills/config" \
    "$stage/skills/run" \
    "$stage/skills/retry" \
    "$stage/references" \
    "$stage/examples"

cp "$SCRIPT_DIR/SKILL.md" "$stage/SKILL.md"
cp "$SCRIPT_DIR/config.example.yaml" "$stage/config.example.yaml"

for skill in setup config run retry; do
    cp "$SCRIPT_DIR/skills/$skill/SKILL.md" "$stage/skills/$skill/SKILL.md"
done

cp "$SCRIPT_DIR"/references/*.md "$stage/references/"
cp "$SCRIPT_DIR"/examples/*.py "$stage/examples/"

config_action="created from config.example.yaml"
if [[ -f "$target/config.yaml" ]]; then
    cp "$target/config.yaml" "$stage/config.yaml"
    config_action="preserved existing config.yaml"
else
    cp "$SCRIPT_DIR/config.example.yaml" "$stage/config.yaml"
fi

for relative_path in "${required_files[@]}" "config.yaml"; do
    [[ -f "$stage/$relative_path" ]] \
        || fail "Staged file not found: $stage/$relative_path"
done

printf 'Installing %s Skill to %s\n' "$SKILL_NAME" "$target"

if [[ -e "$target" ]]; then
    mv "$target" "$backup"
    if ! mv "$stage" "$target"; then
        mv "$backup" "$target"
        fail "Installation failed; previous version was restored."
    fi
    stage=""
    printf 'Previous version backed up to %s\n' "$backup"
else
    mv "$stage" "$target"
    stage=""
fi

[[ -f "$target/SKILL.md" ]] || fail "Installed SKILL.md is missing."
[[ -f "$target/config.yaml" ]] || fail "Installed config.yaml is missing."

printf 'Installation complete. config.yaml was %s.\n' "$config_action"
printf 'Installed files: %s\n' "$target"
printf 'Next: edit %s before running the pipeline.\n' "$target/config.yaml"
