#!/bin/bash
# PDF2MD Skill Installer
# Installs pdf2md skill for Claude Code or Codex

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="pdf2md"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📄 PDF2MD Skill Installer${NC}"
echo "================================"

# Detect agent type
detect_agent() {
    if [ -n "$CLAUDE_CODE" ] || command -v claude &> /dev/null; then
        echo "claude"
    elif command -v codex &> /dev/null; then
        echo "codex"
    else
        echo "unknown"
    fi
}

# Install for Claude Code
install_claude() {
    local target_dir="$HOME/.claude/skills"
    echo -e "${GREEN}✓ Detected Claude Code${NC}"
    echo "Installing to: $target_dir"

    # Create target directory
    mkdir -p "$target_dir"

    # Copy skill directories
    echo "Copying skill files..."
    cp -r "$SCRIPT_DIR/skills/setup" "$target_dir/"
    cp -r "$SCRIPT_DIR/skills/config" "$target_dir/"
    cp -r "$SCRIPT_DIR/skills/run" "$target_dir/"

    # Copy main SKILL.md if it exists
    if [ -f "$SCRIPT_DIR/SKILL.md" ]; then
        cp "$SCRIPT_DIR/SKILL.md" "$target_dir/"
    fi

    echo -e "${GREEN}✅ Installation complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Configure VLM API: Edit your config.yaml"
    echo "  2. Activate environment: conda activate pdf2md"
    echo "  3. Start using: Ask Claude to convert a PDF"
}

# Install for Codex
install_codex() {
    local target_dir="$HOME/.codex/skills"
    echo -e "${GREEN}✓ Detected Codex${NC}"
    echo "Installing to: $target_dir"

    # Create target directory
    mkdir -p "$target_dir"

    # Copy skill directories
    echo "Copying skill files..."
    cp -r "$SCRIPT_DIR/skills/setup" "$target_dir/"
    cp -r "$SCRIPT_DIR/skills/config" "$target_dir/"
    cp -r "$SCRIPT_DIR/skills/run" "$target_dir/"

    # Copy main SKILL.md if it exists
    if [ -f "$SCRIPT_DIR/SKILL.md" ]; then
        cp "$SCRIPT_DIR/SKILL.md" "$target_dir/"
    fi

    echo -e "${GREEN}✅ Installation complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Configure VLM API: Edit your config.yaml"
    echo "  2. Activate environment: conda activate pdf2md"
    echo "  3. Start using: Ask Codex to convert a PDF"
}

# Main installation logic
main() {
    local agent_type="${1:-$(detect_agent)}"

    case "$agent_type" in
        claude)
            install_claude
            ;;
        codex)
            install_codex
            ;;
        unknown)
            echo -e "${RED}✗ No supported agent detected${NC}"
            echo ""
            echo "Please specify agent type: ./install.sh [claude|codex]"
            echo ""
            echo "Or manually install:"
            echo "  cp -r skills/* ~/.claude/skills/  # For Claude Code"
            echo "  cp -r skills/* ~/.codex/skills/   # For Codex"
            exit 1
            ;;
        *)
            echo -e "${RED}✗ Unknown agent type: $agent_type${NC}"
            echo "Supported: claude, codex"
            exit 1
            ;;
    esac

    echo ""
    echo -e "${YELLOW}📚 Documentation:${NC}"
    echo "  - Setup guide: skills/setup/SKILL.md"
    echo "  - Config guide: skills/config/SKILL.md"
    echo "  - Usage guide: skills/run/SKILL.md"
    echo "  - README: README.md"
}

# Run main with all arguments
main "$@"
