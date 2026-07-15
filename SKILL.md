---
name: "pdf2md"
description: "Convert research paper PDFs to Markdown with structured figure data extraction. Extracts panel-level CSV tables or descriptions from scientific figures (CNS-level papers). Use when the user wants to convert a PDF paper to MD with figure data."
---

# PDF to Markdown with Figure Data Extraction

Convert CNS-level research paper PDFs into structured Markdown, with scientific figures decomposed into individual panels and their numerical data extracted as CSV tables.

## Sub-Skills

This project is organized into three sub-skills:

| Skill | Path | Purpose | Trigger When |
|-------|------|---------|-------------|
| **pdf2md-setup** | `skills/setup/SKILL.md` | Environment configuration | Set up conda/uv env, install deps, configure HF mirror, download models |
| **pdf2md-config** | `skills/config/SKILL.md` | VLM API & workflow configuration | Configure API keys, change VLM models, adjust CLI parameters |
| **pdf2md-run** | `skills/run/SKILL.md` | Pipeline execution | Convert a PDF, run the pipeline, check output quality |

## Quick Start

```bash
# 1. Set up environment
conda activate pdf2md   # See skills/setup/SKILL.md

# 2. Configure VLM API
# Edit config.yaml with your API key  # See skills/config/SKILL.md

# 3. Run the pipeline
python examples/pipeline.py /path/to/paper.pdf   # See skills/run/SKILL.md
```

## Project Structure

```
pdf2md-skill/
├── SKILL.md                  # This file — project index
├── config.example.yaml       # VLM config template (tracked by git)
├── config.yaml               # Your VLM config (gitignored)
├── skills/
│   ├── setup/SKILL.md        # Environment setup sub-skill
│   ├── config/SKILL.md       # VLM & workflow config sub-skill
│   └── run/SKILL.md          # Pipeline execution sub-skill
├── references/
│   ├── architecture.md       # Implementation details
│   ├── figure_rules.md       # 9-rule VLM classification prompt
│   └── troubleshooting.md    # Problem-solution lookup
└── examples/
    └── pipeline.py           # Reference implementation (~620 lines)
```

## References

- `skills/setup/SKILL.md` — Environment installation and hardware requirements
- `skills/config/SKILL.md` — VLM API configuration and CLI parameters
- `skills/run/SKILL.md` — 7-step pipeline execution, quality checks, failure strategies
- `references/figure_rules.md` — 9-rule panel classification prompt
- `references/architecture.md` — Implementation details (text truncation fix, VLM response handling, memory management)
- `references/troubleshooting.md` — Problem-solution table
- `examples/pipeline.py` — Complete reference implementation
