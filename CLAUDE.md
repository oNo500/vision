# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目目标

Vision 是面向全职个人创作者的工具集，覆盖短视频与直播两条主线：

- **情报与学习** — 竞品监控、爆款拆解、账号数据追踪、知识库沉淀
- **素材处理** — 格式转换、竖屏适配、批量下载、字幕生成
- **内容生产** — AI 脚本生成（Vertex AI）、TTS 配音
- **分发自动化** — 多平台定时发布
- **选题监控** — 热榜抓取、AI 筛选每日推送
- **直播辅助** — 录播切片、弹幕处理

当前处于**工具阶段**，工具成熟后逐步接入自动化工作流（工程化阶段）。详见 ROADMAP.md。

## 目录结构

```
scripts/
├── intelligence/   情报与学习系统脚本
├── video/          视频处理脚本
├── audio/          音频处理脚本
└── live/           直播相关脚本
docs/               调研文档
data/               输入文件（不入库）
output/             输出结果（不入库）
```

## 文档结构

```
docs/
├── live-streaming-research.md    直播工具详细调研（开源项目、商业SaaS、技术方案）
├── live-streaming-overview.md    直播工具生态 ASCII 总览图
├── douyin-live-starter-guide.md  抖音直播新手指南（资质、算法、选品、违规）
├── how-to-find-real-insights.md  如何收集真实从业经验（方法论）
├── ai-integration-risks.md       直播 AI 集成能力与风险评估（TTS/LLM/数字人）
├── video-production-pipeline.md  短视频制作链路（趋势监控→批量制作→合规复刻→自动分发）
├── ai-video-toolstack.md         AI 辅助视频制作工具栈（脚本/配音/音乐/视觉素材/剪辑/质量审查）
└── solo-creator-playbook.md      个人自由职业创作者完整方案（直播/短视频/变现/工具/AI工作流）
```

## 规范

- 文档内容使用**中文**，代码标识符和 commit message 使用**英文**
- 主分支为 `master`，遵循 GitHub Flow + Conventional Commits
- Markdown 文档可使用 GitHub Alert 语法（`[!NOTE]` / `[!TIP]` / `[!IMPORTANT]` / `[!WARNING]` / `[!CAUTION]`），文档以 GitHub 为渲染目标
