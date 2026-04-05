# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目目标

Vision 是一个面向视觉内容创作的工具集，核心方向：

- **直播能力** — 直播流管理、弹幕互动、实时处理
- **视频剪辑** — 切割、合成、转码、后期处理
- **音频处理** — 提取、降噪、混音、音画同步

当前处于**工具阶段**，工具成熟后逐步接入自动化工作流（工程化阶段）。

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
