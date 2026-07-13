# Architecture & Implementation Details

## Single-Pass Processing

This pipeline processes the entire PDF in one pass to preserve table context.

There is no automatic low-memory fallback. If single-pass processing runs out of memory, stop the run and split the input PDF externally. Process each resulting PDF separately; the pipeline does not merge chunked outputs.

## Figure Numbering After Filtering

When images are filtered out, use **original global indices** for figure numbering, NOT sequential positions. Otherwise figure numbers shift and panels map to wrong figures.

```python
# Correct: use original indices from pictures list
for pic_idx, _, _ in pictures:
    if pic_idx < len(parts) - 1:
        pic_to_fig[pic_idx] = figure_num
        figure_num += 1

# Wrong: sequential positions (breaks after filtering)
for i in range(len(pictures)):
    pic_to_fig[i] = figure_num  # DON'T DO THIS
```

## Text Truncation Fix (3-Step)

When images are filtered out, docling's `<!-- image -->` placeholders still exist. The `parts` array has N+1 elements for N original images. After filtering, `pic_idx` values still point to original positions, causing text to be skipped (e.g., title, authors, abstract on page 1).

**The fix has 3 parts:**

1. **Rebuild `parts` array**: merge text for filtered images into the previous part
2. **Remap `pic_idx`** in `pictures` to sequential (0, 1, 2, ...) matching the new `parts`
3. **Remap downstream dicts** (`figure_panels`, `relabel_map`) to use new indices

```python
parts = md.split("<!-- image -->")

# Step A: Rebuild parts - merge text for filtered images
kept_indices = set(i for i, _, _ in pictures)
new_parts = [parts[0]]  # Always keep first part (text before any image)
for orig_idx in range(1, len(parts)):
    img_idx = orig_idx - 1  # Which image this part boundary corresponds to
    if img_idx in kept_indices:
        new_parts.append(parts[orig_idx])
    else:
        new_parts[-1] = new_parts[-1] + parts[orig_idx]  # Merge filtered image's text
parts = new_parts

# Step B: Remap picture indices to sequential
old_to_new_idx = {}
new_pictures = []
for new_idx, (old_idx, pic, path) in enumerate(pictures):
    old_to_new_idx[old_idx] = new_idx
    new_pictures.append((new_idx, pic, path))
pictures = new_pictures

# Step C: Remap downstream dicts
figure_panels = {old_to_new_idx[k]: v for k, v in figure_panels.items() if k in old_to_new_idx}
relabel_map = {old_to_new_idx[k]: v for k, v in relabel_map.items() if k in old_to_new_idx}
```

After this, `pic_to_fig` and the MD assembly loop use the new sequential indices correctly.

## VLM API Response Handling

The API may return content as string, list, or dict. Always handle all three:

```python
content = resp["choices"][0]["message"]["content"]
if isinstance(content, list):
    content = "\n".join(item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text")
elif isinstance(content, dict):
    content = content.get("text", str(content))
```

## Memory Management

- **Single-pass (default)**: Process entire PDF at once. Requires ~16GB RAM for typical papers (10-20 pages).
- **If OOM occurs**: Stop the run, use a machine with more memory, or split the input PDF before rerunning. This fallback is manual.
- Don't hold all docling results in memory simultaneously if processing multiple PDFs.

## Error Handling

- Network errors (503, proxy): the affected VLM result is recorded as failed; fix connectivity and rerun
- `std::bad_alloc`: stop and reduce the input PDF size or use a machine with more memory
- JSON parse failures: record as error entry, continue with remaining panels
