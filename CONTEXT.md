# PDF2MD Domain Context

- **Conversion Run**: One PDF conversion identified by the input PDF SHA-256 and output directory.
- **Run Manifest**: The durable `run_manifest.json` state for a Conversion Run, including Stage status, artifacts, panel status, and VLM usage.
- **Stage**: A restartable pipeline unit such as parse, filter, panels, descriptions, tables, prepare, extract, or assemble.
- **Figure**: A figure-level image group mapped to one filtered document picture.
- **Panel**: A cropped scientific subplot belonging to a Figure.
- **VLM Client**: The deep module that owns provider requests, response normalization, retries, JSON validation, and usage accounting.
- **Assembled Markdown**: The final Markdown generated only from persisted artifacts and current panel data.
- **Quality Gate**: The automated checks written to `quality_report.json`.
