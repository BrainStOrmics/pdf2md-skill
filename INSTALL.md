# 🚀 Installation Guide | 安装指南

**Quick installation for Claude Code and Codex agents**  
**Claude Code 和 Codex 智能体快速安装**

---

## 📦 One-Line Install | 一键安装

### For Claude Code | Claude Code 用户

```bash
git clone https://github.com/your-repo/pdf2md-skill.git
cd pdf2md-skill
./install.sh claude
```

### For Codex | Codex 用户

```bash
git clone https://github.com/your-repo/pdf2md-skill.git
cd pdf2md-skill
./install.sh codex
```

### Auto-Detect | 自动检测

```bash
git clone https://github.com/your-repo/pdf2md-skill.git
cd pdf2md-skill
./install.sh  # Automatically detects your agent
```

---

## 🔧 Manual Installation | 手动安装

If the installer doesn't work, you can manually copy the skill files:

### Claude Code

```bash
# Copy skill directories
cp -r skills/setup ~/.claude/skills/
cp -r skills/config ~/.claude/skills/
cp -r skills/run ~/.claude/skills/
cp SKILL.md ~/.claude/skills/
```

### Codex

```bash
# Copy skill directories
cp -r skills/setup ~/.codex/skills/
cp -r skills/config ~/.codex/skills/
cp -r skills/run ~/.codex/skills/
cp SKILL.md ~/.codex/skills/
```

---

## ✅ Verify Installation | 验证安装

After installation, verify the skills are available:

### Claude Code

```bash
# Check if skills are installed
ls ~/.claude/skills/

# Should see:
# setup/  config/  run/  SKILL.md
```

### Codex

```bash
# Check if skills are installed
ls ~/.codex/skills/

# Should see:
# setup/  config/  run/  SKILL.md
```

---

## 🎯 Next Steps | 下一步

### 1. Setup Environment | 设置环境

```bash
# Create conda environment | 创建 conda 环境
conda create -n pdf2md python=3.10
conda activate pdf2md

# Install dependencies | 安装依赖
conda install -c conda-forge docling figpanel pymupdf pillow pyyaml numpy requests
```

### 2. Configure VLM API | 配置 VLM API

```bash
# Copy config template | 复制配置模板
cp config.example.yaml config.yaml

# Edit config.yaml with your API credentials
# 编辑 config.yaml 填入你的 API 凭证
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
./install.sh claude  # or codex

# Or manually copy | 或手动复制
cp -r skills/* ~/.claude/skills/
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
