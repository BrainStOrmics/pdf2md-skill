# Setup Guide (from scratch)

## 1. Python Environment

```bash
conda create -n pdf2md python=3.11 -y
conda activate pdf2md
```

Python 3.11+ required. 3.13 also works.

## 2. Install Dependencies

```bash
# Core dependencies
pip install docling pymupdf Pillow requests numpy PyYAML

# Panel detection (YOLOv12-based)
pip install figpanel

# Verify installation
python -c "import docling; print('docling', docling.__version__)"
python -c "import figpanel; print('figpanel OK')"
python -c "import fitz; print('pymupdf', fitz.version)"
```

**Models downloaded on first run (~550MB total):**

- `docling-layout-heron` (~300MB) - document layout analysis
- `TableFormer` (~200MB) - table structure recognition
- `figpanel` YOLOv12 (~50MB) - panel detection

Ensure internet access and ~1GB disk space for first run.

## 3. VLM API Configuration

The pipeline uses an OpenAI-compatible `chat/completions` API. Copy the tracked template and fill in your provider settings:

```powershell
Copy-Item config.example.yaml config.yaml
```

```yaml
runtime:
  offline: false

vlm:
  model: "qwen3.7-plus"
  api_base: "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
  api_key: "your_api_key_here"
```

`config.yaml` is ignored by Git so API keys are not committed. Keep `config.example.yaml` free of real credentials.
Leave `runtime.offline` as `false` on the first run so Docling and figpanel can download their models. Set it to `true` only after all required models are available locally.

The default config path is `config.yaml` in the skill directory. To use a config elsewhere, pass `--config`:

```powershell
python examples/pipeline.py paper.pdf --config C:\path\to\config.yaml
```

The pipeline refuses to reuse a non-empty output directory by default. To rerun into the same directory, pass `--overwrite`; it replaces only the managed `images/`, `panels/`, JSON files, and the current paper's final Markdown.

## 4. Verify Setup

```python
# Test imports (no PDF needed)
python -c "
from docling.document_converter import DocumentConverter
import figpanel
import fitz
print('✓ All imports successful')
print(f'  docling, figpanel, pymupdf loaded')
"

# Validate VLM configuration without sending a request
python -c "from examples.pipeline import load_vlm_config; from pathlib import Path; print(load_vlm_config(Path('config.yaml'))[:2])"
```

If imports fail, run `conda activate pdf2md` first.

## 5. Hardware Requirements

| Resource | Minimum       | Recommended         | Notes                                                |
| -------- | ------------- | ------------------- | ---------------------------------------------------- |
| RAM      | 16GB          | 16GB+               | The pipeline supports single-pass processing only    |
| CPU      | 4 cores       | 8 cores             | docling and figpanel both CPU-compatible             |
| GPU      | Optional      | Optional            | Not required, but speeds up inference                |
| Disk     | 1GB free      | 2GB free            | docling models (~550MB) + temporary files            |
| Network  | Stable        | Stable              | For VLM API calls and first-time model downloads     |
