---
name: "pdf2md-config"
description: "VLM API 与工作流配置 — 配置 VLM 提供商（API key、模型、endpoint）、修改 pipeline 工作流参数、理解输入输出格式。Use when the user needs to configure API keys, change VLM models, adjust pipeline parameters, or understand the I/O contract."
---

# VLM API 与工作流配置 (Configuration)

## Trigger Conditions

Use this skill when the user wants to:
- Configure or change the VLM API provider (API key, model, endpoint)
- Switch between different VLM models (e.g., qwen, gpt-4o, claude)
- Adjust pipeline parameters (output directory, filter threshold, overwrite behavior)
- Understand the input/output file structure
- Toggle between online and offline runtime modes

## VLM API Configuration

The pipeline uses an **OpenAI-compatible `chat/completions` API**. Copy the tracked template and fill in your provider settings:

```bash
cp config.example.yaml config.yaml
```

Then edit `config.yaml`:

```yaml
runtime:
  offline: false

vlm:
  model: "qwen3.7-plus"
  api_base: "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
  api_key: "your_api_key_here"
```

### Config Fields

| Field | Description | Example |
|-------|-------------|---------|
| `vlm.model` | Model name for the chat/completions API | `"qwen3.7-plus"`, `"gpt-4o"`, `"claude-sonnet-4-20250514"` |
| `vlm.api_base` | Base URL of the OpenAI-compatible API endpoint | `"https://api.openai.com/v1"` |
| `vlm.api_key` | API key for authentication | `"sk-..."` |
| `vlm.enable_thinking` | Optional provider-specific thinking switch; omit for standard OpenAI-compatible requests | `false` |
| `runtime.offline` | If `true`, blocks all network access to HF (use after models are downloaded) | `false` / `true` |

### Supported VLM Providers

Any OpenAI-compatible endpoint works. Common choices:

| Provider | `api_base` | `model` |
|----------|-----------|---------|
| Aliyun DashScope | `https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` | `qwen3.7-plus` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| Anthropic (via proxy) | Your proxy URL | `claude-sonnet-4-20250514` |
| Local (Ollama) | `http://localhost:11434/v1` | `llava:latest` |

### Security Note

`config.yaml` is listed in `.gitignore` so API keys are never committed. Keep `config.example.yaml` free of real credentials — it serves as the tracked template.

## Runtime Offline Mode

| Mode | When to use |
|------|------------|
| `offline: false` | **Default.** Required on first run to download docling and figpanel models from Hugging Face. |
| `offline: true` | Set after all models are cached locally. Blocks all HF network access for air-gapped environments. |

## CLI Parameters

The pipeline (`examples/pipeline.py`) accepts these arguments:

```bash
python examples/pipeline.py <pdf_path> [options]
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pdf` | (required) | Path to the input PDF file |
| `--config` | `<skill_dir>/config.yaml` | Path to VLM config file |
| `--output` / `-o` | `<pdf_name>-with-csv` | Output directory |
| `--overwrite` | `false` | Replace managed files in a non-empty output directory |
| `--resume` | `false` | Resume completed Stages and panel checkpoints from `run_manifest.json` |
| `--filter-size` | `30` | Minimum image size in KB (images smaller than this are discarded as logos/icons) |
| `--keep-original-images` | `false` | Keep original `pic_*.png` files in `images/` directory (by default they are deleted after panel extraction) |

### Examples

```bash
# Basic usage
python examples/pipeline.py paper.pdf

# Custom output directory
python examples/pipeline.py paper.pdf -o results/paper_output

# Use a config from a different location
python examples/pipeline.py paper.pdf --config /path/to/config.yaml

# Rerun into the same directory (replaces previous output)
python examples/pipeline.py paper.pdf --overwrite

# Resume an interrupted run
python examples/pipeline.py paper.pdf -o output/ --resume

# Lower the size threshold to keep smaller images
python examples/pipeline.py paper.pdf --filter-size 10

# Keep original extracted images (pic_*.png) for debugging or reuse
python examples/pipeline.py paper.pdf --keep-original-images
```

## Input/Output Contract

### Input

A scientific paper PDF (CNS-level, multi-figure, multi-panel).

### Output

```
output/
├── {paper}_complete.md    # Final MD (text + figures + structured data)
├── panels_data.json       # Raw CSV extraction results
├── run_manifest.json      # Durable Stage and panel state
├── quality_report.json    # Automated quality gate report
├── docling.md             # Parsed document before figure assembly
├── panels/                # Individual panel images (Figure{N}_Panel{X}.png)
├── descriptions.json      # VLM-generated captions per panel
└── images/                # Original extracted images (full figures without panels)
```

`--overwrite` and `--resume` are mutually exclusive. The `--overwrite` flag only replaces the pipeline's managed files (`images/`, `panels/`, JSON files, parsed Markdown, and the final Markdown). Other files in the output directory are not touched.
