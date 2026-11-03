---
name: "pdf2md-run"
description: "运行 PDF 转 Markdown pipeline — 执行 7 步转换流程（PDF 解析、图片过滤、面板检测、描述生成、表格提取、CSV 提取、MD 组装）、质量检查、故障处理。Use when the user wants to convert a PDF paper to Markdown, run the pipeline, or check output quality."
---

# Pipeline 运行 (Run)

## Trigger Conditions

Use this skill when the user wants to:
- Convert a research paper PDF to Markdown with structured figure data
- Run the pdf2md pipeline on a PDF file
- Extract numerical data from scientific figures
- Check output quality or troubleshoot pipeline issues

## Prerequisites

Before running the pipeline, ensure:
1. **Environment is set up** — see `skills/setup/SKILL.md` (or use the `pdf2md-setup` skill)
2. **Config is ready** — see `skills/config/SKILL.md` (or use the `pdf2md-config` skill)
3. `config.yaml` exists with valid VLM API credentials
4. `runtime.offline: false` until all local models have been downloaded

## Quick Start

```bash
conda activate pdf2md
python examples/pipeline.py /path/to/paper.pdf

# Resume an interrupted run from run_manifest.json
python examples/pipeline.py /path/to/paper.pdf -o output/ --resume
```

The reference implementation is `examples/pipeline.py`. For CLI options, see the [config skill](../config/SKILL.md#cli-parameters).

## 7-Step Pipeline

### Step 1: PDF Parsing (docling, single-pass)

Process entire PDF in one pass. Single-pass preserves table structure context.
- Requires ~16GB RAM for papers up to 20 pages
- This implementation has no automatic low-memory fallback. If OOM occurs, stop and split the input PDF before rerunning.
- Docling `partial_success`, `failure`, or `skipped` statuses mark the `parse` Stage as failed; do not continue with an incomplete document.

### Step 2: Image Filtering

- **Size filter**: discard images < 30KB (logos, icons). Threshold configurable via `--filter-size`.
- **VLM filter**: ask the VLM "Is this a scientific figure? YES/NO" to remove non-scientific images (ads, decorations).

### Step 3: Panel Detection (figpanel)

Detect sub-panels within each figure, crop as individual PNG. Tracking uses **original image indices**.
- Based on YOLOv12 model
- Panels smaller than 50x50 pixels or with confidence < 0.3 are discarded
- Low-variance panels (uniform color) are discarded
- Text captions at the bottom of panels are trimmed automatically

### Step 4: Panel Caption Generation

VLM generates an English caption per panel:
- Identifies the sub-panel label (A, B, C, ...) from the upper-left corner
- Handles relabeling when detected labels differ from positional labels
- Falls back to a simpler prompt for figures without detectable panels

### Step 5: Image-Based Table Extraction

VLM re-extracts tables that docling marked as "bad" (dot-pattern, no readable text).
- Only tables where all cells contain dots and there are ≤2 cells are re-extracted
- Uses the original page image from PyMuPDF for higher quality

### Step 6: Panel CSV Data Extraction

VLM applies the 9-rule classification prompt (see `references/figure_rules.md`).
Output: JSON Array per panel with `fig_type`, `data_type`, `content`.
- Each completed panel is checkpointed atomically to `panels_data.json` and `run_manifest.json`.
- On `--resume`, valid panel results are reused and only missing or failed panels are retried.

The 9 rules classify figures into:
1. No-extract (qualitative images, schematics)
2. Proportion/composition (pie charts, stacked bars)
3. High-dimensional data (bubble plots, line charts, heatmaps → num_table)
4. Statistical distributions (boxplots, violin plots)
5. Forest plots / survival curves
6. Plain scatter plots
7. FACS flow cytometry
8. Dendrograms / Circos plots
9. Other complex figures

### Step 7: Markdown Assembly

Insert figure panels + structured data at `<!-- image -->` placeholders. Replace captions with VLM-generated descriptions.
- Panels are renamed to `Figure{N}_Panel{X}.png`
- Full images (no panels detected) are named `Figure{N}_full.png`
- Bad tables are replaced with VLM-extracted Markdown tables
- `examples/assemble_md.py` is the single assembler used by both normal runs and retries.
- A quality gate writes `quality_report.json` and checks image links, unresolved placeholders, panel results, descriptions, and error entries.

Use a new or empty output directory. Pass `--overwrite` only when replacing this pipeline's managed outputs from an earlier run.

## Run State and Resume

Every run writes `run_manifest.json`. It records the PDF SHA-256, Stage status, parsed document, filtered pictures, figure/panel mapping, extracted tables, panel checkpoints, and VLM usage.

- Completed Stages are skipped when `--resume` is used.
- Stage 6 writes a checkpoint after each panel.
- The PDF hash must match the existing run.
- `--overwrite` and `--resume` are mutually exclusive.
- `examples/resume_step6.py output/` is a convenience wrapper around `pipeline.py --resume`.

## Quality Checks

After generating the output MD, verify:

1. **First page**: Title, authors, abstract are present (not truncated)
2. **Last page**: References/license present (not truncated)
3. **Middle text**: No gaps from filtered images (check text continuity)
4. **Figure count**: All figures and panels correctly inserted
5. **CSV quality**: Spot-check 2-3 panels for correct data_type and content
6. **Table headers**: Paper's own tables have proper headers (not just numbers)
7. **Automated gate**: Confirm `quality_report.json` has `"ok": true`

## Failure Strategies

| Failure | Strategy |
|---------|----------|
| VLM API 400 error | Record as error, continue with remaining panels |
| JSON parse failure | Record as error entry, skip that panel |
| OOM (`std::bad_alloc`) | Stop; use more memory or split the input PDF before rerunning |
| Network timeout | VLMClient retries with exponential backoff; then record the failed panel |
| Malformed JSON | VLMClient validates the JSON array schema and retries the request |
| Figure misclassified | Iterate on prompt rules in `references/figure_rules.md` |

**Expected error rates**: ~10% VLM 400 errors, ~3-5% JSON parse failures. These are normal.
For papers >50 pages or >200 panels, expect timeouts — split into smaller chunks.

## Automatic Retry Workflow | 自动重试流程

**IMPORTANT: Always run automatic retry after pipeline completion!**  
**重要：在 pipeline 完成后始终运行自动重试！**

After running the standard pipeline, the agent MUST automatically:

1. **Check for failures | 检查失败**
   ```bash
   python examples/check_failures.py <output_dir>
   ```

2. **If failures exist, retry them | 如果存在失败，重试它们**
   ```bash
   python examples/retry_failures.py --parallel 5 <output_dir>
   ```

3. **Re-check and report | 重新检查并报告**
   ```bash
   python examples/check_failures.py <output_dir>
   ```

4. **If still failures, retry again (up to 3 times total) | 如果仍有失败，再次重试（最多 3 次）**

`retry_failures.py` automatically reassembles the final Markdown and reruns the quality gate after successful repairs.

### Agent Instructions | 智能体指令

When the user asks to convert a PDF, the agent should:

1. Run the standard pipeline
2. **Automatically check for failures** (do NOT ask the user)
3. **Automatically retry failures** (do NOT ask the user)
4. Report the final success rate
5. Only if failures persist after 3 retries, inform the user

**Example Agent Behavior | 智能体行为示例**

```
User: Convert paper.pdf to Markdown

Agent:
1. Runs: python examples/pipeline.py paper.pdf -o output/
2. Runs: python examples/check_failures.py output/
   → Found 15 failures
3. Runs: python examples/retry_failures.py --parallel 5 output/
   → Fixed 12, 3 still failed
4. Runs: python examples/retry_failures.py --parallel 5 output/
   → Fixed 2, 1 still failed
5. Runs: python examples/retry_failures.py --parallel 5 output/
   → Fixed 1, 0 failed
6. Reports: ✅ Conversion complete! 100% success rate after 3 retries.
```

**Key Points | 关键点**

- ✅ Always check for failures automatically
- ✅ Always retry failures automatically
- ✅ Use parallel processing for faster retries
- ✅ Retry up to 3 times
- ✅ Only inform user if failures persist after all retries
- ❌ Do NOT ask user "should I retry?" - just do it
- ❌ Do NOT stop after first pipeline run if there are failures

## Reference Files

| File | Purpose |
|------|---------|
| `examples/pipeline.py` | Complete reference implementation (single-pass, CLI arguments) |
| `examples/check_failures.py` | Check for failed panel extractions |
| `examples/retry_failures.py` | Retry failed panels with parallel processing |
| `examples/assemble_md.py` | Unified Markdown assembly and quality gate |
| `examples/run_manifest.py` | Durable Stage and panel state |
| `examples/vlm_client.py` | Centralized VLM retries, response normalization, and JSON validation |
| `examples/resume_step6.py` | Resume a run from `run_manifest.json` |
| `references/figure_rules.md` | 9-rule panel classification prompt (Chinese) |
| `references/architecture.md` | Implementation details (text truncation fix, VLM response handling, memory management) |
| `references/troubleshooting.md` | Problem-solution lookup table |
