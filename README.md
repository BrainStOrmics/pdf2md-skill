# 📄 PDF to Markdown Converter

**Convert research papers to structured Markdown with figure data extraction**  
**将科研论文 PDF 转换为结构化 Markdown，并提取图表数据**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Pipeline](https://img.shields.io/badge/pipeline-7%20steps-orange.svg)](#-pipeline-overview)

---

## 🌟 Features | 功能特性

- 🔬 **Scientific Figure Parsing** | 科学图表解析  
  Decompose multi-panel figures into individual panels with intelligent detection  
  智能检测并分解多面板图表为独立子图

- 📊 **Automated Data Extraction** | 自动数据提取  
  Extract numerical data from charts as CSV tables using VLM (Vision-Language Models)  
  使用视觉语言模型从图表中提取数值数据为 CSV 表格

- 📝 **Structured Markdown Output** | 结构化 Markdown 输出  
  Generate clean, readable Markdown with embedded figures and data tables  
  生成包含图表和数据表格的清晰可读的 Markdown 文档

- ⚡ **Parallel Processing** | 并行处理  
  Process multiple panels simultaneously for faster conversion (10x speedup)  
  同时处理多个面板，加快转换速度（10倍加速）

- 🔄 **Automatic Error Recovery** | 自动错误恢复  
  Automatically detect and retry failed panels due to network errors (up to 3 times)  
  自动检测并重试因网络错误失败的面板（最多 3 次）

- 🛠️ **Modular Pipeline** | 模块化流程  
  7-step pipeline with checkpoint support for resuming interrupted runs  
  7 步流程，支持断点续传

- 🤖 **Agent-Ready** | 智能体就绪  
  Fully automatic workflow: pipeline → check → retry → report, no manual intervention needed  
  全自动工作流：pipeline → 检查 → 重试 → 报告，无需人工干预

---

## 🎯 Automatic Workflow | 自动化工作流

**The agent handles everything automatically - just ask to convert a PDF!**  
**智能体自动处理一切 - 只需要求转换 PDF！**

```
┌─────────────────────────────────────────────────────────────┐
│  User Request: "Convert paper.pdf to Markdown"              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Run Pipeline                                       │
│  python examples/pipeline.py paper.pdf -o output/           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: Check Failures (Automatic)                         │
│  python examples/check_failures.py output/                  │
│  → Found 15 failures                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Retry Failures (Automatic, Parallel)               │
│  python examples/retry_failures.py --parallel 5 output/     │
│  → Fixed 12, 3 still failed                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: Retry Again (Up to 3 times)                        │
│  → Fixed 2, 1 still failed                                  │
│  → Fixed 1, 0 failed ✅                                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5: Report Results                                     │
│  ✅ Conversion complete! 100% success rate                  │
└─────────────────────────────────────────────────────────────┘
```

**Key Benefits | 关键优势:**
- ✅ **Zero Manual Intervention** | 零人工干预  
  No need to check for failures or manually retry  
  无需检查失败或手动重试

- ✅ **Parallel Retries** | 并行重试  
  Uses `--parallel 5` for faster recovery  
  使用 `--parallel 5` 加快恢复速度

- ✅ **Smart Retry Logic** | 智能重试逻辑  
  Up to 3 retry attempts, only reports if still failing  
  最多 3 次重试，仅在仍然失败时报告

- ✅ **Network Error Handling** | 网络错误处理  
  Automatically recovers from ~10-20% typical network errors  
  自动恢复约 10-20% 的典型网络错误

---

## 📦 Installation | 安装

**Quick install for Claude Code and Codex agents**  
**Claude Code 和 Codex 智能体快速安装**

```bash
# Clone and install | 克隆并安装
git clone https://github.com/your-repo/pdf2md-skill.git
cd pdf2md-skill
./install.sh  # Auto-detects your agent
```

📚 **See [INSTALL.md](INSTALL.md) for detailed instructions**  
📚 **详细安装说明请查看 [INSTALL.md](INSTALL.md)**

---

## 🚀 Quick Start | 快速开始

### 🤖 Agent Usage | 智能体使用

**Use with Claude Code or Codex for conversational PDF conversion**  
**使用 Claude Code 或 Codex 进行对话式 PDF 转换**

#### Example 1: Basic Conversion | 基本转换

```
You: 将 ~/PDFs/raw/paper.pdf 转换为 Markdown
You: Convert ~/PDFs/raw/paper.pdf to Markdown

Agent:
  1. [Runs pipeline] python examples/pipeline.py paper.pdf -o output/
  2. [Checks failures] python examples/check_failures.py output/
     → Found 15 failures
  3. [Retries automatically] python examples/retry_failures.py --parallel 5 output/
     → Fixed 12, 3 still failed
  4. [Retries again] python examples/retry_failures.py --parallel 5 output/
     → Fixed 2, 1 still failed
  5. [Retries again] python examples/retry_failures.py --parallel 5 output/
     → Fixed 1, 0 failed

Agent: ✅ 转换完成！100% 成功率（经过 3 次自动重试）
Agent: ✅ Conversion complete! 100% success rate (after 3 automatic retries)
```

**💡 Agent automatically retries failures - no need to ask!**  
**💡 智能体会自动重试失败 - 无需询问！**

#### Example 2: Batch Processing | 批量处理

```
You: 将 ~/PDFs/raw/ 下的所有 PDF 转换为 Markdown
You: Convert all PDFs in ~/PDFs/raw/ to Markdown

Agent:
  1. [Processes each PDF with pipeline]
  2. [Automatically checks and retries each PDF]
  3. [Reports final results]

Agent: ✅ 完成！已处理 11 个 PDF 文件，所有失败已自动修复
Agent: ✅ Complete! Processed 11 PDFs, all failures automatically fixed
```

#### Example 3: Parallel Processing | 并行处理

```
You: 使用 24 个并行进程处理 ~/PDFs/raw/Booeshaghi_2021.pdf，保留原始图片
You: Process ~/PDFs/raw/Booeshaghi_2021.pdf with 24 parallel workers, keep original images

Agent: [Configures parallel processing and runs pipeline]
Agent: ✅ 处理完成！38 个面板，保留 14 张原始图片
```

#### Example 4: Error Handling & Retry | 错误处理与重试

```
You: 检查处理状态，如果有失败的 PDF，重新处理它们
You: Check processing status and retry any failed PDFs

Agent: [Checks logs, identifies failures, retries failed conversions]
Agent: ✅ 所有 PDF 处理成功
```

#### Example 5: Subagent Delegation | 子智能体委托

```
You: 主任务完成后，将剩余的 6 个 PDF 分配给 6 个子智能体并行处理
You: After the main task completes, delegate the remaining 6 PDFs to 6 subagents for parallel processing

Agent: [Spawns 6 subagents, each handling one PDF]
Agent: ✅ 所有子任务完成
```

**💡 Tip:** The agent automatically detects and uses the pdf2md skills based on your request!  
**💡 提示：** 智能体根据你的请求自动检测并使用 pdf2md 技能！

---

### 💻 CLI Usage | 命令行使用

**Direct command-line usage for automation and scripts**  
**用于自动化和脚本的直接命令行使用**

#### 1️⃣ Setup Environment | 设置环境

```bash
# Activate conda environment | 激活 conda 环境
conda activate pdf2md

# Or set up from scratch | 或从头开始设置
# See skills/setup/SKILL.md for detailed instructions
```

#### 2️⃣ Configure API | 配置 API

```bash
# Copy config template | 复制配置模板
cp config.example.yaml config.yaml

# Edit with your API credentials | 编辑填入你的 API 凭证
# See skills/config/SKILL.md for provider options
```

#### 3️⃣ Run Pipeline | 运行流程

```bash
# Basic usage | 基本用法
python examples/pipeline.py paper.pdf -o output/

# With parallel processing | 使用并行处理
export PDF2MD_PARALLEL_WORKERS=10
python examples/pipeline.py paper.pdf -o output/

# Keep original images | 保留原始图片
python examples/pipeline.py paper.pdf -o output/ --keep-original-images

# Batch processing | 批量处理
for pdf in ~/PDFs/raw/*.pdf; do
    name=$(basename "$pdf" .pdf)
    python examples/pipeline.py "$pdf" -o "~/PDFs/processed/$name/"
done
```

#### 4️⃣ Error Recovery & Retry | 错误恢复与重试

**Check for failed panels | 检查失败的面板**

```bash
# Check all processed PDFs | 检查所有已处理的 PDF
python examples/check_failures.py ~/PDFs/processed/

# Check specific PDF | 检查特定 PDF
python examples/check_failures.py ~/PDFs/processed/Tang_2025/
```

**Retry failed panels | 重试失败的面板**

```bash
# Retry all failures | 重试所有失败
python examples/retry_failures.py ~/PDFs/processed/

# Retry with parallel processing | 使用并行处理重试
python examples/retry_failures.py --parallel 5 ~/PDFs/processed/

# Retry specific PDF | 重试特定 PDF
python examples/retry_failures.py --pdf Tang_2025 ~/PDFs/processed/

# Dry run (show what would be retried) | 试运行（显示将要重试的内容）
python examples/retry_failures.py --dry-run ~/PDFs/processed/
```

**💡 Tip:** Network errors (~10-20%) are normal. Use retry to fix failed panels without reprocessing the entire PDF!  
**💡 提示：** 网络错误（~10-20%）是正常的。使用重试功能修复失败的面板，无需重新处理整个 PDF！

📚 **See [skills/retry/SKILL.md](skills/retry/SKILL.md) for detailed retry guide**  
📚 **详细重试指南请查看 [skills/retry/SKILL.md](skills/retry/SKILL.md)**

---

## 📋 Pipeline Overview | 流程概览

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: PDF Parsing (docling)                              │
│  ├─ Single-pass document conversion                         │
│  └─ Extract images, tables, text                            │
├─────────────────────────────────────────────────────────────┤
│  Step 2: Image Filtering                                    │
│  ├─ Size filter (>30KB)                                     │
│  └─ VLM filter (scientific figure detection)                │
├─────────────────────────────────────────────────────────────┤
│  Step 3: Panel Detection (figpanel)                         │
│  ├─ YOLOv12-based sub-panel detection                       │
│  └─ Crop and save individual panels                         │
├─────────────────────────────────────────────────────────────┤
│  Step 4: Panel Captions                                     │
│  └─ VLM generates descriptions for each panel               │
├─────────────────────────────────────────────────────────────┤
│  Step 5: Image-Based Tables                                 │
│  └─ Re-extract bad tables using page images                 │
├─────────────────────────────────────────────────────────────┤
│  Step 6: Panel CSV Extraction ⚡ (PARALLEL)                 │
│  ├─ Classify figures using 9-rule prompt                    │
│  ├─ Extract numerical data as CSV                           │
│  └─ Process all panels in parallel (10x faster!)            │
├─────────────────────────────────────────────────────────────┤
│  Step 7: Markdown Assembly                                  │
│  └─ Combine text, figures, and data into final MD           │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure | 项目结构

```
pdf2md-skill/
├── examples/
│   ├── pipeline.py           # Main pipeline script | 主流程脚本
│   ├── check_failures.py     # Check failed panels | 检查失败面板
│   ├── retry_failures.py     # Retry failed panels | 重试失败面板
│   └── resume_step6.py       # Resume interrupted runs | 断点续传脚本
├── skills/
│   ├── setup/SKILL.md        # Environment setup | 环境设置
│   ├── config/SKILL.md       # Configuration guide | 配置指南
│   ├── run/SKILL.md          # Pipeline execution | 流程执行
│   └── retry/SKILL.md        # Retry failed panels | 重试失败面板
├── references/
│   ├── figure_rules.md       # 9-rule classification prompt | 9规则分类提示
│   ├── architecture.md       # Implementation details | 实现细节
│   └── troubleshooting.md    # Common issues & solutions | 常见问题与解决方案
├── config.yaml               # VLM API configuration | VLM API 配置
├── config.example.yaml       # Configuration template | 配置模板
└── README.md                 # This file | 本文件
```

---

## ⚙️ Configuration | 配置

### VLM API Setup | VLM API 设置

Edit `config.yaml` with your provider settings:

```yaml
runtime:
  offline: false

vlm:
  model: "qwen3.7-plus"
  api_base: "https://your-api-endpoint.com/v1"
  api_key: "your-api-key-here"
```

**Supported Providers | 支持的提供商**:
- 🟢 Aliyun DashScope (通义千问)
- 🟢 OpenAI (GPT-4o)
- 🟢 Anthropic (Claude)
- 🟢 Local Ollama

### CLI Parameters | 命令行参数

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pdf` | (required) | Path to input PDF |
| `--output` / `-o` | `<pdf>-with-csv` | Output directory |
| `--config` | `config.yaml` | VLM config file path |
| `--overwrite` | `false` | Replace existing output |
| `--filter-size` | `30` | Min image size (KB) |
| `--keep-original-images` | `false` | Keep `pic_*.png` files |

### Environment Variables | 环境变量

| Variable | Default | Description |
|----------|---------|-------------|
| `PDF2MD_PARALLEL_WORKERS` | `10` | Max parallel API calls |
| `HF_ENDPOINT` | - | Hugging Face mirror URL |

---

## 📊 Output Structure | 输出结构

```
output/
├── paper_complete.md          # Final Markdown | 最终 Markdown
├── panels_data.json           # Raw CSV data | 原始 CSV 数据
├── descriptions.json          # Panel captions | 面板描述
├── panels/                    # Individual panels | 独立面板
│   ├── Figure1_PanelA.png
│   ├── Figure1_PanelB.png
│   └── ...
└── images/                    # Original images (if kept) | 原始图片（如保留）
    ├── pic_000.png
    └── ...
```

---

## 🔧 Advanced Usage | 高级用法

### Parallel Processing | 并行处理

Speed up Step 6 (panel CSV extraction) with parallel API calls:

```bash
# Use 20 parallel workers | 使用 20 个并行工作线程
export PDF2MD_PARALLEL_WORKERS=20
python examples/pipeline.py paper.pdf -o output/
```

**Performance | 性能**:
- 115 panels: ~30 min → ~3 min (10x faster!) 🚀
- 66 panels: ~17 min → ~1.7 min

### Resume Interrupted Runs | 恢复中断的运行

If the pipeline is interrupted at Step 6:

```bash
# Resume from checkpoint | 从断点恢复
python examples/resume_step6.py output/
```

### Custom Figure Rules | 自定义图表规则

Edit `references/figure_rules.md` to customize the 9-rule classification prompt for panel CSV extraction.

---

## 📖 Quick Reference | 快速参考

### For Agent Users | 智能体用户

```
Just ask: "Convert paper.pdf to Markdown"
Agent will: Pipeline → Check → Retry (3x) → Report ✅
```

### For CLI Users | 命令行用户

```bash
# 1. Setup | 设置
conda activate pdf2md

# 2. Convert | 转换
python examples/pipeline.py paper.pdf -o output/

# 3. Check & Retry | 检查并重试
python examples/check_failures.py output/
python examples/retry_failures.py --parallel 5 output/
```

### Common Commands | 常用命令

```bash
# Convert with parallel processing | 并行转换
PDF2MD_PARALLEL_WORKERS=20 python examples/pipeline.py paper.pdf -o output/

# Keep original images | 保留原始图片
python examples/pipeline.py paper.pdf -o output/ --keep-original-images

# Batch convert | 批量转换
for pdf in ~/PDFs/raw/*.pdf; do python examples/pipeline.py "$pdf" -o "~/PDFs/processed/$(basename "$pdf" .pdf)/"; done

# Check failures | 检查失败
python examples/check_failures.py ~/PDFs/processed/

# Retry all failures | 重试所有失败
python examples/retry_failures.py --parallel 10 ~/PDFs/processed/
```

---

## 🐛 Troubleshooting | 故障排除

### Common Issues | 常见问题

**VLM API Errors | VLM API 错误**
- ~10% timeout/error rate is normal
- Pipeline continues processing remaining panels
- Failed panels are logged in output

**Memory Issues | 内存问题**
- Papers >20 pages: requires ~16GB RAM
- If OOM occurs, split PDF into smaller chunks

**Slow Processing | 处理缓慢**
- Increase `PDF2MD_PARALLEL_WORKERS`
- Check API rate limits
- Use `--keep-original-images` to skip image deletion

See `references/troubleshooting.md` for more details.

---

## 📚 Documentation | 文档

Detailed documentation is organized into sub-skills:

| Skill | Path | Purpose |
|-------|------|---------|
| 🛠️ Setup | `skills/setup/SKILL.md` | Environment configuration |
| ⚙️ Config | `skills/config/SKILL.md` | API & parameter configuration |
| ▶️ Run | `skills/run/SKILL.md` | Pipeline execution with automatic retry |
| 🔄 Retry | `skills/retry/SKILL.md` | Automatic error recovery and retry |

---

## 🤝 Contributing | 贡献

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

## 📝 License | 许可证

MIT License - see LICENSE file for details

---

## 🙏 Acknowledgments | 致谢

- [docling](https://github.com/DS4SD/docling) - PDF parsing
- [figpanel](https://github.com/your-repo/figpanel) - Panel detection
- [Hugging Face](https://huggingface.co/) - Model hosting

---

<div align="center">

**Made with ❤️ for scientific research**

**为科学研究而制 ❤️**

</div>
