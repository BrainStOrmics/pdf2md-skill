---
name: "pdf2md"
description: "Convert research paper PDFs to Markdown with structured figure data extraction. Extracts panel-level CSV tables or descriptions from scientific figures (CNS-level papers). Use when the user wants to convert a PDF paper to MD with figure data."
---

# PDF to Markdown with Figure Data Extraction

## Trigger Conditions

Use this skill when the user wants to:
- Convert a research paper PDF to Markdown with structured figure data
- Extract numerical data from scientific figures (heatmaps, boxplots, scatter plots, etc.)
- Replace figure captions with CSV tables or descriptions based on figure type

## Input/Output Contract

**Input:** A scientific paper PDF (CNS-level, multi-figure, multi-panel)

**Output:**
```
output/
├── {paper}_complete.md    # Final MD (text + figures + structured data)
├── panels_data.json       # Raw CSV extraction results
├── panels/                # Individual panel images
├── descriptions.json      # VLM-generated captions
└── images/                # Original extracted images
```

## Execution Steps

### Prerequisites

If environment not set up, read `references/setup.md` first.
Review `examples/pipeline.py` as the reference implementation.
Copy `config.example.yaml` to `config.yaml` and fill in the VLM provider settings before running the pipeline. Never put real credentials in `config.example.yaml`.
Keep `runtime.offline: false` until all local models have been downloaded.

### Step 1: PDF Parsing (docling, single-pass)

Process entire PDF in one pass. Single-pass preserves table structure context.
- Requires ~16GB RAM for papers up to 20 pages
- This implementation has no automatic low-memory fallback. If OOM occurs, stop and split the input PDF before rerunning.

### Step 2: Image Filtering

- Size filter: discard < 30KB (logos, icons)
- VLM filter: ask "Is this a scientific figure? YES/NO"

### Step 3: Panel Detection (figpanel)

Detect sub-panels, crop as individual PNG. Track using **original image indices**.

### Step 4: Panel Caption Generation

VLM generates English caption per panel. Handle relabeling (e.g., B→A).

### Step 5: Image-Based Table Extraction

VLM re-extracts tables docling marked as "bad" (dot-pattern, no text).

### Step 6: Panel CSV Data Extraction

VLM applies the 9-rule classification prompt (see `references/figure_rules.md`).
Output: JSON Array with `fig_type`, `data_type`, `content`.

### Step 7: Markdown Assembly

Insert figure panels + structured data at `<!-- image -->` placeholders. Replace captions.
Use a new or empty output directory. Pass `--overwrite` only when replacing this pipeline's managed outputs from an earlier run.

## Quality Checks

After generating the output MD, verify:

1. **First page**: Title, authors, abstract are present (not truncated)
2. **Last page**: References/license present (not truncated)
3. **Middle text**: No gaps from filtered images (check text continuity)
4. **Figure count**: All figures and panels correctly inserted
5. **CSV quality**: Spot-check 2-3 panels for correct data_type and content
6. **Table headers**: Paper's own tables have proper headers (not just numbers)

## Failure Strategies

| Failure | Strategy |
|---------|----------|
| VLM API 400 error | Record as error, continue with remaining panels |
| JSON parse failure | Record as error entry, skip that panel |
| OOM (`std::bad_alloc`) | Stop; use more memory or split the input PDF before rerunning |
| Network timeout | Record the failed VLM result; fix connectivity and rerun |
| Figure misclassified | Iterate on prompt rules in `references/figure_rules.md` |

**Expected error rates**: ~10% VLM 400 errors, ~3-5% JSON parse failures. These are normal.
For papers >50 pages or >200 panels, expect timeouts — split into smaller chunks.

## References

- `references/setup.md` — Environment installation and hardware requirements
- `references/figure_rules.md` — 9-rule panel classification prompt
- `references/architecture.md` — Implementation details (text truncation fix, VLM response handling, memory management)
- `references/troubleshooting.md` — Problem-solution table
- `examples/pipeline.py` — Complete reference implementation (single-pass, CLI arguments)
