# Architecture & Implementation Details

## Single-Pass Processing

This pipeline processes the entire PDF in one pass to preserve table context.

There is no automatic low-memory fallback. If single-pass processing runs out of memory, stop the run and split the input PDF externally. Process each resulting PDF separately; the pipeline does not merge chunked outputs.

## Run Manifest and Stages

`run_manifest.json` is the durable state for a Conversion Run. It records:

- Input PDF path and SHA-256
- Stage status
- Parsed Markdown and original picture list
- Filtered picture list and bad-table references
- Figure/panel mapping and descriptions
- Extracted table Markdown
- Per-panel checkpoint status
- VLM usage

Stages are restartable: `parse`, `filter`, `panels`, `descriptions`, `tables`, `prepare`, `extract`, and `assemble`. `pipeline.py --resume` skips completed Stages and only retries missing or failed panels.

All state files are written through a temporary file and `os.replace`, so an interrupted write cannot leave a partially serialized JSON file.

## Figure and Picture Indices

Two indices are retained:

- `docling_index` identifies the original picture and its `<!-- image -->` placeholder.
- `picture_index` is the sequential position after filtering and determines `Figure{N}`.

The assembler uses `docling_index` to rebuild text around filtered placeholders and `picture_index` to order figures. This prevents text truncation without losing the relationship between a Figure and its panels.

Docling can return `partial_success` after page-level preprocessing failures. The pipeline treats every status other than `success` as a failed `parse` Stage, records the errors in the manifest, and stops instead of assembling an incomplete document.

## Text Truncation Fix (3-Step)

Docling emits one `<!-- image -->` placeholder per original picture. When a picture is filtered out, `assemble_md.py` merges that placeholder's following text into the previous part. The filtered figures are then inserted in sequential order using their persisted `docling_index`.

This keeps titles, authors, abstracts, middle text, and references continuous even when many decorative images are removed.

## VLM Client

`vlm_client.py` is the single Interface for vision-model calls. It owns:

- OpenAI-compatible request payload construction
- Optional `enable_thinking`
- String/list/dict response normalization
- Retry with exponential backoff for 429, 5xx, timeouts, empty responses, and malformed JSON
- JSON extraction and required panel fields
- Token usage accounting

Callers only request text or a validated JSON array. Provider-specific behavior and response repair stay inside this Module.

## Markdown Assembler and Quality Gate

`assemble_md.py` is the only Markdown assembler. Normal runs and retries both call it.

The quality gate writes `quality_report.json` and checks:

- Missing image links
- Unresolved `<!-- image -->` placeholders
- Panel error entries
- Panels without extraction results or descriptions
- Empty or unexpectedly short Markdown
- Missing references near the end of the document

## VLM API Response Handling

The API may return content as a string, list, or dictionary. `VLMClient.normalize_content()` handles all three formats before callers receive text.

## Memory Management

- **Single-pass (default)**: Process entire PDF at once. Requires ~16GB RAM for typical papers (10-20 pages).
- **If OOM occurs**: Stop the run, use a machine with more memory, or split the input PDF before rerunning. This fallback is manual.
- Don't hold all docling results in memory simultaneously if processing multiple PDFs.

## Error Handling

- Network errors (429, 5xx, proxy): `VLMClient` retries with exponential backoff
- Empty or malformed responses: retried and schema-validated
- `std::bad_alloc`: stop and reduce the input PDF size or use a machine with more memory
- Persistent panel failure: record an error entry and update `run_manifest.json`
- Interrupted extraction: resume from the latest per-panel checkpoint
