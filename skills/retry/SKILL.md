# PDF2MD 重试修复技能 (Retry & Fix Skill)

## ⚠️ Agent 自动使用 | Automatic Agent Usage

**IMPORTANT: This skill is automatically used by agents after the standard pipeline!**  
**重要：智能体在标准 pipeline 后会自动使用此技能！**

Agents MUST automatically:
1. Run the standard pipeline (see `skills/run/SKILL.md`)
2. Check for failures using `check_failures.py`
3. Retry failures using `retry_failures.py` (up to 3 times)
4. Report final results

**Do NOT ask the user if they want to retry - just do it automatically!**  
**不要询问用户是否要重试 - 自动执行！**

---

## 概述

专门用于修复 PDF2MD 流程中因网络问题导致的图片解析失败。自动检测失败的 panels 并重新调用 VLM API 进行数据提取。

**This is part of the standard workflow - agents use it automatically after pipeline completion.**  
**这是标准工作流的一部分 - 智能体在 pipeline 完成后自动使用。**

## 使用场景

- 运行标准 pipeline 后，发现部分 panels 解析失败（fig_type="error"）
- 网络超时、API 限流、临时服务不可用等问题
- 需要批量修复多个 PDF 的失败 panels

## 快速开始

```bash
# 激活环境
conda activate pdf2md

# 检查失败情况
python examples/check_failures.py ~/PDFs/processed/

# 重试所有失败的 panels
python examples/retry_failures.py ~/PDFs/processed/

# 只重试特定 PDF
python examples/retry_failures.py ~/PDFs/processed/Tang_2025/
```

## 工作原理

### 1. 检测失败

扫描 `panels_data.json` 文件，查找 `fig_type="error"` 的记录：

```json
{
  "Figure2_PanelA.png": [
    {
      "fig_type": "error",
      "data_type": "description",
      "content": "HTTPSConnectionPool... timeout"
    }
  ]
}
```

### 2. 智能重试

- 从 `descriptions.json` 获取 panel 的 caption
- 通过统一的 `VLMClient` 重新调用 VLM API
- 自动处理指数退避、429/5xx、空响应和非法 JSON
- 使用相同的 9-rule prompt
- 自动更新 `panels_data.json`

### 3. 错误处理

- 自动重试机制（可配置重试次数）
- 请求间隔避免 API 限流
- 详细的错误日志
- 跳过已成功的 panels
- 更新 `run_manifest.json` 中的面板状态和 VLM 用量
- 修复成功后自动调用 `assemble_md.py` 重建 Markdown
- 自动重跑 `quality_report.json` 对应的质量门禁

## 命令行参数

```bash
python examples/retry_failures.py [options] <processed_dir>

参数：
  processed_dir          处理结果目录（包含多个 PDF 子目录）

选项：
  --max-retries N        最大重试次数（默认：3）
  --delay SECONDS        请求间隔秒数（默认：0.5）
  --parallel N           并行处理数（默认：1）
  --pdf NAME             只处理指定 PDF（可多次指定）
  --dry-run              只检查不重试
  --verbose              详细输出
```

## 示例

### 检查所有 PDF 的失败情况

```bash
python examples/check_failures.py ~/PDFs/processed/
```

输出：
```
📊 失败统计 | Failure Summary
============================================================
总失败数 | Total failures: 132
失败PDF数 | PDFs with failures: 12

📄 Ashuach_2023: 7 failures
  - Figure2_PanelA.png: HTTPSConnectionPool... timeout
  - Figure2_PanelD.png: HTTPSConnectionPool... timeout
  ...

📄 Tang_2025: 44 failures
  - Figure10_PanelB.png: HTTPSConnectionPool... timeout
  ...
```

### 重试所有失败

```bash
python examples/retry_failures.py ~/PDFs/processed/
```

### 并行重试（加速处理）

```bash
python examples/retry_failures.py ~/PDFs/processed/ --parallel 5
```

### 只重试特定 PDF

```bash
python examples/retry_failures.py ~/PDFs/processed/ --pdf Tang_2025 --pdf Zhang_2024
```

### 先检查再决定

```bash
# 查看失败详情
python examples/retry_failures.py ~/PDFs/processed/ --dry-run

# 确认无误后重试
python examples/retry_failures.py ~/PDFs/processed/
```

## 与主流程集成

推荐工作流：

```bash
# 1. 运行标准 pipeline
python examples/pipeline.py paper.pdf -o output/

# 2. 检查失败情况
python examples/check_failures.py output/

# 3. 如果有失败，运行重试
python examples/retry_failures.py output/

# 4. 重试脚本会自动重建 Markdown；
#    也可以单独运行质量检查与重组：
python examples/assemble_md.py output/
```

## 注意事项

- 重试会覆盖原有的 error 记录
- 建议先使用 `--dry-run` 检查
- 大量失败时建议使用并行模式
- 网络不稳定时可增加 `--delay` 参数
- 新版本重试成功后会自动重新组装 Markdown，不需要手动执行

## 故障排除

### 重试仍然失败

- 检查网络连接
- 检查 API 配额
- 增加 `--delay` 参数
- 查看具体错误信息

### API 限流

- 减少 `--parallel` 参数
- 增加 `--delay` 参数（如 2.0）
- 等待一段时间后重试

### 某些 panels 始终失败

- 可能是图片质量问题
- 检查 `descriptions.json` 中的 caption
- 手动编辑 `panels_data.json`

## 相关文件

- `examples/retry_failures.py` - 重试脚本
- `examples/check_failures.py` - 检查脚本
- `examples/assemble_md.py` - Markdown 重组脚本
- `examples/run_manifest.py` - 持久化运行状态
- `examples/vlm_client.py` - 统一 VLM 请求与重试
- `config.yaml` - VLM API 配置
- `references/figure_rules.md` - 9-rule prompt

## 参见

- [Pipeline 运行指南](../run/SKILL.md) - 标准流程
- [配置指南](../config/SKILL.md) - API 配置
- [环境设置](../setup/SKILL.md) - 环境准备
