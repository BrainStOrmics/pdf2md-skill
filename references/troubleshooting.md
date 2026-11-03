# Troubleshooting Guide

## Common Problems

| Problem | Solution |
|---------|----------|
| `std::bad_alloc` or OOM during docling | Stop the run. Use a machine with more memory or split the input PDF before rerunning; this fallback is not automatic. |
| Heatmap returns description instead of num_table | Rule 3b has explicit prohibition. Check prompt is included. |
| Scatter plot with error bars returns description | Rules 4/6 boundary. Rule 4 must include "带 Error bar 的散点图". |
| Figure numbering wrong (Figure0 appears) | The persisted figure map is inconsistent. Inspect `figures` in `run_manifest.json` and rerun the `prepare` Stage. |
| Title/authors/abstract missing from MD | Parts array not rebuilt after image filtering. See `architecture.md` → Text Truncation Fix. |
| Text in middle of MD missing | Filtered images' text not merged into parts array. |
| Panel count mismatch between steps | Old files in the output directory. Re-run with `--overwrite` to replace pipeline-managed outputs. |
| VLM returns dict/list instead of string | `VLMClient` normalizes all supported response formats. See `architecture.md` → VLM Client. |
| Network proxy errors | `VLMClient` retries transient failures with exponential backoff before recording a panel error. |
| `run_manifest.json` not found | Start a new run without `--resume`, or restore the manifest from the original output directory. |
| PDF hash mismatch | The output directory belongs to a different PDF. Use a new output directory. |
| Quality gate failed | Inspect `quality_report.json`; common causes are missing panel images, unresolved placeholders, or failed panel extractions. |

## Expected Error Rates

When processing papers, expect the following VLM API error rates (these are normal):

- **400 Bad Request**: ~10% of panels (2-3 out of 28) - model rejects certain image formats
- **JSON parse failures**: ~3-5% of panels (1 out of 28) - model returns malformed JSON
- **Timeouts**: Papers >50 pages or >200 panels may timeout due to API call volume. Consider splitting large papers.
