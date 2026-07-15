---
name: "pdf2md-setup"
description: "环境配置 — 搭建 pdf2md 运行所需的 conda/uv 环境、安装依赖、配置 HF 中国镜像、预下载模型。Use when the user needs to set up the environment, install dependencies, fix import errors, or download models."
---

# 环境配置 (Environment Setup)

## Trigger Conditions

Use this skill when the user wants to:
- Set up the pdf2md environment from scratch
- Install or fix Python dependencies
- Configure Hugging Face China mirror for model downloads
- Pre-download required AI models
- Verify that all imports work correctly
- Troubleshoot import errors or missing libraries

## Step 1: Create Python Environment

### Option A: Conda (Recommended)

```bash
conda create -n pdf2md python=3.11 -y
conda activate pdf2md
```

Python 3.11+ required. 3.13 also works.

### Option B: uv

```bash
uv venv .venv --python 3.11
source .venv/bin/activate
```

## Step 2: Install Dependencies

```bash
# Core dependencies
pip install docling pymupdf Pillow requests numpy PyYAML

# Panel detection (YOLOv12-based)
pip install figpanel
```

### OpenCV Headless Fix

If you encounter `ImportError: libXext.so.6: cannot open shared object file` when importing figpanel (via OpenCV), replace the full OpenCV with the headless variant:

```bash
pip uninstall opencv_python -y
pip install opencv-python-headless
```

The headless version provides identical functionality without requiring X11/GUI libraries, which is appropriate for server environments.

## Step 3: Configure Hugging Face China Mirror

For users in China (or when huggingface.co is slow/blocked), set the mirror endpoint **before** downloading models:

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### Make it Persistent in Conda

To auto-set the mirror every time the conda environment is activated:

```bash
mkdir -p $CONDA_PREFIX/etc/conda/activate.d
mkdir -p $CONDA_PREFIX/etc/conda/deactivate.d

echo 'export HF_ENDPOINT=https://hf-mirror.com' > $CONDA_PREFIX/etc/conda/activate.d/hf_mirror.sh
echo 'unset HF_ENDPOINT' > $CONDA_PREFIX/etc/conda/deactivate.d/hf_mirror.sh
```

## Step 4: Pre-Download Models

Models are downloaded automatically on first use (~550MB total). To pre-download explicitly:

```bash
python -c "
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

# Trigger docling model downloads
pipeline_opts = PdfPipelineOptions(do_ocr=False, do_table_structure=True, generate_picture_images=False)
converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts)})
print('docling models OK')

# Trigger figpanel model download
import figpanel
try:
    figpanel.detect('/dev/null')
except:
    pass
print('figpanel model OK')
"
```

**Models downloaded:**

| Model | Size | Purpose |
|-------|------|---------|
| `docling-layout-heron` | ~300MB | Document layout analysis |
| `TableFormer` | ~200MB | Table structure recognition |
| `figpanel` YOLOv12 | ~50MB | Panel detection |

Ensure ~1GB disk space and stable internet for first run.

## Step 5: Verify Installation

```python
python -c "
from importlib.metadata import version
print('docling', version('docling'))
import figpanel; print('figpanel OK')
import fitz; print('pymupdf', fitz.version)
import PIL; print('Pillow OK')
import yaml; print('PyYAML OK')
import numpy; print('numpy OK')
print('All imports successful')
"
```

If `figpanel` import fails with `libXext.so.6` error, apply the [OpenCV Headless Fix](#opencv-headless-fix) above.

## Hardware Requirements

| Resource | Minimum       | Recommended         | Notes                                                |
| -------- | ------------- | ------------------- | ---------------------------------------------------- |
| RAM      | 16GB          | 16GB+               | Single-pass processing requires sufficient memory    |
| CPU      | 4 cores       | 8 cores             | docling and figpanel both CPU-compatible             |
| GPU      | Optional      | Optional            | Not required, but speeds up inference                |
| Disk     | 1GB free      | 2GB free            | Models (~550MB) + temporary files                    |
| Network  | Stable        | Stable              | For VLM API calls and first-time model downloads     |
