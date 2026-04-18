# RAG 话术库 Web UI 设计

## 背景

RAG 话术库已经跑通(`feat/session-memory-and-litellm` 分支),但只有
CLI。对"多个方案多类目录多文件"的场景来说,每次手工 `rag_cli build`
不友好,且看不到索引状态、无法快速观测 `rag_miss` 事件。

## 目标

- 每个 plan 一个 RAG 面板,URL:`/plans/[id]/rag`
- 可视化:列文件、chunk 数、上次 build 时间、rag_miss 计数
- 维护(档位 1):上传 md/txt、删除文件、手动 rebuild
- 不做:在线编辑(用本地编辑器)、版本历史、软删、图片管理

## 非目标(MVP 外)

- 在线 markdown 编辑器
- 文件重命名(直接在本地 rename)
- 跨 plan 话术库共享
- 向量库内容直接 CRUD(必须走"改文件 → rebuild")
- 直播页 rag_miss 角标(后置)

---

## 架构

```
apps/web/src/app/(dashboard)/plans/[id]/
├── page.tsx                  现有:产品/人设/脚本 tabs
└── rag/
    └── page.tsx              NEW:RAG 面板(新增第四个 tab,或独立路由)

apps/web/src/features/live/
├── components/
│   └── rag-panel/
│       ├── index.tsx                  面板壳
│       ├── file-list.tsx              文件列表
│       ├── upload-dropzone.tsx        拖拽上传
│       └── rag-status-card.tsx        meta 指标卡
└── hooks/
    └── use-rag.ts                     CRUD + SSE miss 监听

src/live/
└── rag_routes.py             NEW:FastAPI /live/plans/{id}/rag/*
```

## 后端 API(`/live/plans/{plan_id}/rag`)

全部路由基于 `/live/plans/{plan_id}/rag` 前缀,复用现有 plan prefix 语义。

| 方法 | 路径 | 行为 |
|---|---|---|
| GET | `/` | 索引状态:meta.json + "待索引"标志 |
| GET | `/files` | 列出 `data/talk_points/<plan_id>/` 下所有已知类别的文件 |
| POST | `/files` | 上传单个文件(multipart),指定 `category` |
| DELETE | `/files/{category}/{filename}` | 硬删 |
| POST | `/rebuild` | 触发 `cmd_build(plan_id)`,后台任务 |
| GET | `/rebuild/status` | 轮询:是否在 build、最近一次结束时间/错误 |

### GET /

```json
{
  "indexed": true,                    // 是否存在 .rag/<plan_id>/
  "dirty": true,                      // 文件比索引新(有上传/删除未 rebuild)
  "chunk_count": 312,
  "build_time": "2026-04-18T12:00:00Z",
  "file_count": 14,
  "sources": [
    {
      "rel_path": "scripts/opening.md",
      "category": "scripts",
      "chunks": 4,
      "sha256": "abc...",
      "indexed": true
    },
    {
      "rel_path": "scripts/new-file.md",
      "category": "scripts",
      "chunks": 0,
      "sha256": "def...",
      "indexed": false                // dirty 来源
    }
  ]
}
```

`dirty` 计算:`any(file.sha256 not in meta.sources) or any(meta.source not in file_list)`。

### POST /files

- multipart/form-data
- form fields:`category`(四个值之一),`file`(二进制)
- 拒绝非 `.md` / `.txt`
- 重名:直接覆盖,返回 `{"overwritten": true}`
- 返回 201 + 新文件信息

### DELETE /files/{category}/{filename}

- 硬删物理文件
- **不**删除索引中的 chunks(让用户点 rebuild 才生效,保持显式)
- 返回 204

### POST /rebuild

- 异步启动 `cmd_build(plan_id)`(FastAPI BackgroundTasks)
- 写状态到 `app.state.rag_builds[plan_id]`(in-memory dict)
- 返回 202

### GET /rebuild/status

```json
{
  "running": false,
  "last_build_time": "2026-04-18T12:00:00Z",
  "last_error": null
}
```

### EventBus 事件

`rag_miss` 事件已在 `SessionManager` 发出,前端可订阅,但**MVP 不展示**
(延到直播页面做)。本 spec 只在 UI 里展示**静态计数**(如有),不订阅实
时流。

---

## 前端

### 入口

**方案 A:方案编辑器新增第四个 tab "话术库"**
- 优点:和产品/人设/脚本同级,用户路径短
- 缺点:文件列表在 tab 里可能挤

**方案 B:独立路由 `/plans/[id]/rag`,方案编辑器顶部加"话术库"链接**
- 优点:页面空间宽敞
- 缺点:多一次点击

**决定:B**。话术库内容量大(文件列表 + 上传区 + 状态卡),拆到独立路由
更合理。方案编辑器顶部加一个按钮跳转。

### 页面结构(`/plans/[id]/rag`)

```
┌────────────────────────────────────────┐
│  ← 方案编辑          [重建索引] dirty  │  Header
├────────────────────────────────────────┤
│  [指标卡:14 文件 / 312 chunks /      │
│   2h 前 build / 0 miss]               │
├────────────────────────────────────────┤
│  [拖拽上传区:选类别 + 拖文件]         │
├────────────────────────────────────────┤
│  📁 scripts (5)                        │
│    opening.md       4 chunks   ✓ / 🗑  │
│    product.md       6 chunks   ✓ / 🗑  │
│    new.md           待索引     ✗ / 🗑  │
│  📁 competitor_clips (3)               │
│    ...                                 │
│  📁 product_manual (4)                 │
│    ...                                 │
│  📁 qa_log (2)                         │
│    ...                                 │
└────────────────────────────────────────┘
```

### 组件

- **`<RagPanel>`** 壳
- **`<RagStatusCard>`** 指标卡(file_count / chunk_count / last_build / miss_count)
- **`<UploadDropzone>`** 拖拽区,含类别下拉
- **`<FileList>`** 按 category 分组,每行 rel_path + chunk 数 + 状态 + 删除按钮
- **`<RebuildButton>`** 顶部按钮,`dirty=true` 时高亮红色角标

### Hook

```ts
// apps/web/src/features/live/hooks/use-rag.ts
export function useRag(planId: string) {
  return {
    status,           // GET /rag 的结果 + dirty 计算
    files,            // sources[]
    upload,           // (file: File, category) => Promise<void>
    remove,           // (category, filename) => Promise<void>
    rebuild,          // () => Promise<void>
    buildStatus,      // {running, last_build_time, last_error}
    loading,
    refetch,
  }
}
```

轮询策略:
- `buildStatus` 在 rebuild 期间每 1.5s 轮询直到 `running=false`
- 其他字段常驻,upload/delete/rebuild 后手动 refetch

### 样式

遵循现有 `PageHeader` + `Button` + `Input` + `shadcn` 风格,不额外引依赖。
Dropzone 用原生 `onDragOver/onDrop`,不引 react-dropzone。

### 二次确认

- 删除文件 → shadcn AlertDialog(已在用)
- 覆盖上传同名 → 后端 200 OK + toast "已覆盖 <filename>"
- 删除所有文件 → 需要 rebuild 才能清空索引,提示用户

---

## 错误与边界情况

| 场景 | 行为 |
|---|---|
| plan 不存在 | 404 |
| 上传非 md/txt | 400,toast 报错 |
| 上传超过 5MB | 400,toast 报错("单文件最大 5MB") |
| rebuild 正在跑时再触发 | 409,toast "索引构建中,请稍候" |
| data/talk_points/<plan_id>/ 不存在 | GET / 自动创建;upload 时 mkdir -p |
| 索引目录不存在(从未 build) | `indexed=false`,页面显示"尚未建立索引,点击重建" |
| ChromaDB 加载异常 | 500,前端 toast + 提示检查 `.rag/<plan_id>/` 权限 |
| 并发删除+rebuild | 删除是同步,rebuild 是后台 — 删除先于 rebuild 生效,rebuild 时发现文件少了会清理对应 chunks |

---

## 安全性

- **所有路径按 `Path.resolve()` 校验不跳出 `DATA_ROOT / plan_id`**(防 path traversal)
- 文件名用 `re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5._-]', '_', name)` 清洗
- 本项目目前**无身份认证**(单用户本地服务),MVP 暂不加
- CORS 已配置仅 localhost

---

## 测试

### 后端(`src/live/rag_routes_test.py`)

- GET / 空 plan → `indexed=false`
- GET / 已 build → `indexed=true`,chunk_count 正确
- POST /files 上传 → 文件落到 `data/talk_points/<plan_id>/<category>/`
- POST /files 重名 → 覆盖,`overwritten=true`
- POST /files 非法后缀 → 400
- POST /files 非法类别 → 400
- DELETE 存在的文件 → 204,文件消失
- DELETE 不存在 → 404
- POST /rebuild → 202,状态变 running
- POST /rebuild 运行中再调 → 409
- Path traversal 尝试(`../../../etc/passwd`) → 400

### 前端(`apps/web/src/features/live/components/rag-panel/__tests__/`)

- `<UploadDropzone>` 拖文件 → 触发 upload callback,分类正确
- `<FileList>` 删除按钮 → 弹 dialog → 确认 → 触发 remove
- `<RagStatusCard>` dirty=true → rebuild 按钮高亮
- `useRag` rebuild 调用 → 轮询 buildStatus → 完成后 refetch

---

## 实施步骤(TDD,顺序可 review)

1. **后端路由 + 测试** — `src/live/rag_routes.py` + test
2. **挂到 app** — main.py include_router
3. **前端 hook + 测试** — `use-rag.ts` 对着 mock API
4. **UI 组件** — RagPanel / FileList / UploadDropzone / StatusCard
5. **路由页面** — `app/(dashboard)/plans/[id]/rag/page.tsx`
6. **方案编辑器跳转按钮** — 顶部加"话术库" link
7. **手工 E2E** — 起后端 + 前端,完整操作一遍

---

## 影响面

| 文件 | 改动 | 行数 |
|---|---|---|
| `src/live/rag_routes.py` | 新建 | ~200 |
| `src/live/rag_routes_test.py` | 新建 | ~180 |
| `src/api/main.py` | include rag_router + rag_builds state | +5 |
| `src/live/rag_cli.py` | `cmd_build` 可被外部调用(已是纯函数,无改) | 0 |
| `apps/web/src/features/live/hooks/use-rag.ts` | 新建 | ~120 |
| `apps/web/src/features/live/components/rag-panel/*` | 新建 4 个组件 | ~400 |
| `apps/web/src/app/(dashboard)/plans/[id]/rag/page.tsx` | 新建 | ~60 |
| `apps/web/src/app/(dashboard)/plans/[id]/page.tsx` | 加顶部跳转链接 | +8 |
| `apps/web/src/config/app-paths.ts` | 加 `dashboard.planRag(id)` | +3 |

合计 ~980 行(含测试 ~260 行)。

---

## 风险

| 风险 | 对策 |
|---|---|
| rebuild 期间 UI 阻塞感强 | 后端异步;UI 轮询 + 显示进度("正在索引 scripts/opening.md ...") |
| 用户同时开两个 tab 上传冲突 | 文件系统最后写入者赢;rebuild 基于最新状态 |
| 大文件上传(50MB 以上) | MVP 限制 5MB;超出 413 |
| ChromaDB 进程锁 | 若 SessionManager 正在用 RAG,rebuild 时 build 会覆盖;MVP 文档提示"重建索引会短暂中断直播检索" |
| bge-base 首次 rebuild 慢(下载模型) | 路由返回 202,前端显示"首次构建,下载模型中(~2 分钟)",不设超时 |

---

## 后置工作(不在本 spec 范围)

- 直播页实时 rag_miss 角标(订阅 EventBus SSE)
- 文件重命名 API
- 跨 plan 话术库共享
- 上传 zip 批量导入
- web 内 markdown 编辑器(档位 2)
- 索引构建进度条(需要 cmd_build 暴露进度回调)
