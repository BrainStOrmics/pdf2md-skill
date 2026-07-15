# GOTCHA: Davis_2024.pdf Pipeline Run

## Original Error
```
docling-parse could not load document... Failed to load document (PDFium: Data format error)
```

## Root Cause
The file was **missing** from the expected location (`~/PDFs/raw/Davis_2024.pdf`). It existed at `/home/xq/BIA-Benchmark/data/raw/Davis_2024.pdf` instead. The PDF itself is valid:
- 3.7 MB, PDF 1.4, proper `%PDF-1.4` header
- 15 pages, all readable via PyMuPDF
- Title: "KIR+CD8+ T cells suppress pathogenic T cells and are active in autoimmune diseases and COVID-19"
- Produced by iText 4.2.0

## Resolution
Copied the file from BIA-Benchmark to `~/PDFs/raw/`:
```bash
cp /home/xq/BIA-Benchmark/data/raw/Davis_2024.pdf ~/PDFs/raw/Davis_2024.pdf
```

## Pipeline Run Notes

### Timeout Issues
- The pipeline was killed **twice** by the 10-minute command timeout during Step 6 (Panel CSV Extraction), which processes 31 panels via VLM API calls.
- Fix: ran with `nohup ... &` to bypass the timeout.
- Total runtime: ~80 minutes.

### VLM API Timeouts (Step 6)
Two panels failed CSV extraction due to VLM API read timeouts (`token-plan.cn-beijing.maas.aliyuncs.com`):
- `Figure8_PanelD.png` — timeout
- `Figure8_PanelE.png` — timeout

These panels have captions but **no CSV data** in the final output.

## Final Output
| File | Size |
|------|------|
| `~/PDF/processed/Davis_2024/Davis_2024_complete.md` | 109,448 bytes |
| `~/PDF/processed/Davis_2024/panels_data.json` | 19,439 bytes |
| `~/PDF/processed/Davis_2024/descriptions.json` | 16,396 bytes |
| Panels directory | 31 panel images |

### Stats
- Pages: 15
- Pictures: 11 (after filtering 2 non-scientific figures)
- Panels detected: 31
- Captions extracted: 31
- Tables: 1 (image-based, page 10)
- CSV extracted from panels: 29/31 (2 VLM timeouts)
