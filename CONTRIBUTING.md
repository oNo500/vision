# Contributing Guide

## 环境准备

### 依赖工具

| 工具 | 用途 | 安装 |
|------|------|------|
| [uv](https://docs.astral.sh/uv/) | Python 版本与依赖管理 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [fnm](https://github.com/Schniz/fnm) | Node 版本管理 | `brew install fnm` |
| [pnpm](https://pnpm.io/) | Node 包管理 | `npm install -g pnpm` |

### 初始化

```bash
# Python 环境
uv sync

# Node 环境（有 Node 脚本时）
fnm use        # 自动读取 .nvmrc
pnpm install
```

---

## 目录结构

```
scripts/
├── video/    # 视频处理脚本
├── audio/    # 音频处理脚本
└── live/     # 直播相关脚本
data/         # 输入文件（不入库）
output/       # 输出结果（不入库）
```

---

## 新增脚本

### Python 脚本

在对应目录下新建 `.py` 文件，顶部说明脚本用途和用法：

```python
#!/usr/bin/env python3
"""
trim.py — 裁剪视频片段

用法:
    uv run scripts/video/trim.py input.mp4 --start 10 --end 30
"""
```

运行方式：

```bash
uv run scripts/video/trim.py
```

### Node 脚本

在对应目录下新建 `.mjs` 或 `.ts` 文件：

```bash
node scripts/video/trim.mjs
# 或
pnpm tsx scripts/video/trim.ts
```

---

## 依赖管理

### 添加 Python 依赖

```bash
uv add yt-dlp          # 运行时依赖
uv add --dev ruff      # 开发依赖
```

### 添加 Node 依赖

```bash
pnpm add execa         # 运行时依赖
pnpm add -D typescript # 开发依赖
```

---

## 调试

### Python 脚本

```bash
# 直接运行，观察输出
uv run scripts/video/trim.py

# 进入交互式环境调试
uv run python -c "
import scripts.video.trim as t
# 手动调用函数
"

# 加断点（推荐）
# 在代码中插入：
import pdb; pdb.set_trace()
```

### 查看依赖环境

```bash
uv run python -c "import sys; print(sys.executable)"  # 确认用的是哪个 Python
uv pip list                                            # 查看已安装的包
```

---

## 代码规范

Python 使用 ruff 做格式化和 lint：

```bash
make lint      # 检查
make format    # 自动修复
```

> [!TIP]
> 脚本放 `data/` 读输入、写结果到 `output/`，避免污染源码目录。
