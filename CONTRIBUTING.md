# Contributing Guide

## 环境准备

### 依赖工具

请按照各工具官网说明安装：

| 工具 | 用途 | 官网 |
|------|------|------|
| uv | Python 版本与依赖管理 | https://docs.astral.sh/uv/getting-started/installation/ |
| fnm | Node 版本管理 | https://github.com/Schniz/fnm#installation |
| pnpm | Node 包管理 | https://pnpm.io/installation |

### 初始化

```bash
make install
```

---

## 目录结构

```
src/
├── api/            # FastAPI 服务（路由、依赖注入、配置）
├── live/           # 直播控场 Agent
├── video/          # 视频处理
├── audio/          # 音频处理
├── intelligence/   # 情报与学习系统
└── shared/         # 跨模块共享（EventBus、DB）
apps/
└── web/            # Next.js 前端（直播控场 Web UI）
data/               # 输入文件（不入库）
output/             # 输出结果（不入库）
```

---

## 开发

### 启动服务

```bash
make api    # FastAPI 后端 → localhost:8000
make web    # Next.js 前端 → localhost:3000
```

两个命令需要分别在独立终端中运行。

### 测试

```bash
make test          # 运行所有 Python 测试
make test-watch    # 监听模式
```

### 代码规范

```bash
make lint      # 检查（Python + 前端）
make format    # 自动格式化（Python + 前端）
```

---

## 依赖管理

### Python 依赖

```bash
uv add yt-dlp          # 运行时依赖
uv add --dev ruff      # 开发依赖
```

### Node 依赖

```bash
pnpm --filter web add <package>        # 前端运行时依赖
pnpm --filter web add -D <package>     # 前端开发依赖
```

---

## 新增模块

### Python 模块（`src/`）

在对应子目录新建 `.py` 文件，顶部说明用途：

```python
"""
module.py — 简短描述

用法:
    uv run python -m vision_live.module
"""
```

测试文件与源文件同目录放置（`foo.py` + `foo_test.py`）。

### 前端页面（`apps/web/`）

路由文件放 `src/app/(dashboard)/` 路由组下，业务逻辑下沉到 `src/features/`。
