# 🚀 Installation Guide | 安装指南

**Quick installation for Claude Code and Codex agents**  
**Claude Code 和 Codex 智能体快速安装**

---

## 📦 One-Line Install | 一键安装

### For Claude Code | Claude Code 用户

```bash
git clone https://github.com/your-repo/pdf2md-skill.git
cd pdf2md-skill
bash install.sh claude
```

### For Codex | Codex 用户

```bash
git clone https://github.com/your-repo/pdf2md-skill.git
cd pdf2md-skill
bash install.sh codex
```

### Auto-Detect | 自动检测

```bash
git clone https://github.com/your-repo/pdf2md-skill.git
cd pdf2md-skill
bash install.sh  # Automatically detects your agent
```

---

## 🔧 Manual Installation | 手动安装

If the installer doesn't work, you can manually copy the skill files:

### Claude Code

```bash
mkdir -p ~/.claude/skills/pdf2md/skills
mkdir -p ~/.claude/skills/pdf2md/references
mkdir -p ~/.claude/skills/pdf2md/examples
cp SKILL.md config.example.yaml ~/.claude/skills/pdf2md/
cp -R skills/* ~/.claude/skills/pdf2md/skills/
cp references/*.md ~/.claude/skills/pdf2md/references/
cp examples/*.py ~/.claude/skills/pdf2md/examples/
cp config.example.yaml ~/.claude/skills/pdf2md/config.yaml
```

### Codex

```bash
mkdir -p ~/.codex/skills/pdf2md/skills
mkdir -p ~/.codex/skills/pdf2md/references
mkdir -p ~/.codex/skills/pdf2md/examples
cp SKILL.md config.example.yaml ~/.codex/skills/pdf2md/
cp -R skills/* ~/.codex/skills/pdf2md/skills/
cp references/*.md ~/.codex/skills/pdf2md/references/
cp examples/*.py ~/.codex/skills/pdf2md/examples/
cp config.example.yaml ~/.codex/skills/pdf2md/config.yaml
```

---

## ✅ Verify Installation | 验证安装

After installation, verify the skills are available:

### Claude Code

```bash
test -f ~/.claude/skills/pdf2md/SKILL.md
test -f ~/.claude/skills/pdf2md/skills/retry/SKILL.md
test -f ~/.claude/skills/pdf2md/examples/pipeline.py
test -f ~/.claude/skills/pdf2md/references/figure_rules.md
```

### Codex

```bash
test -f ~/.codex/skills/pdf2md/SKILL.md
test -f ~/.codex/skills/pdf2md/skills/retry/SKILL.md
test -f ~/.codex/skills/pdf2md/examples/pipeline.py
test -f ~/.codex/skills/pdf2md/references/figure_rules.md
```

---

## 🎯 Next Steps | 下一步

### 1. Setup Environment | 设置环境

```bash
# Create conda environment | 创建 conda 环境
conda create -n pdf2md python=3.11
conda activate pdf2md

# Install dependencies | 安装依赖
conda install -c conda-forge docling figpanel pymupdf pillow pyyaml numpy requests
```

### 2. Configure VLM API | 配置 VLM API

```bash
# Edit the installed config with your API credentials
# 编辑安装目录中的 config.yaml 填入你的 API 凭证
```

### 3. Start Using | 开始使用

**For Claude Code:**
```
You: 将 ~/PDFs/raw/paper.pdf 转换为 Markdown
Claude: [Uses pdf2md skills to convert the PDF]
```

**For Codex:**
```
You: Convert ~/PDFs/raw/paper.pdf to Markdown
Codex: [Uses pdf2md skills to convert the PDF]
```

---

## 🐛 Troubleshooting | 故障排除

### Issue: Skills not found | 问题：找不到技能

**Solution | 解决方案**:
```bash
# Re-run installer | 重新运行安装器
bash install.sh claude  # or codex
```

### Issue: Conda environment not found | 问题：找不到 conda 环境

**Solution | 解决方案**:
```bash
# Create environment | 创建环境
conda create -n pdf2md python=3.10
conda activate pdf2md

# Install dependencies | 安装依赖
pip install docling figpanel pymupdf pillow pyyaml numpy requests
```

### Issue: VLM API errors | 问题：VLM API 错误

**Solution | 解决方案**:
- Check `config.yaml` has valid API credentials
- Verify API endpoint is accessible
- Check network connectivity

---

## 📚 Documentation | 文档

- **[Setup Guide](skills/setup/SKILL.md)** - Detailed environment setup
- **[Config Guide](skills/config/SKILL.md)** - API and parameter configuration
- **[Usage Guide](skills/run/SKILL.md)** - Pipeline execution guide
- **[README](README.md)** - Project overview and examples

---

<div align="center">

**Need help? Check the [README](README.md) or open an issue!**

**需要帮助？查看 [README](README.md) 或提交 issue！**

</div>
