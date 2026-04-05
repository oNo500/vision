# 直播工具调研

## 开源工具（GitHub）

### 弹幕抓取

| 项目 | 语言 | Stars | 说明 |
|------|------|-------|------|
| [DouyinLiveWebFetcher](https://github.com/saermart/DouyinLiveWebFetcher) | Python | ~1.7k | 网页版弹幕实时抓取，持续维护 |
| [DouyinBarrageGrab](https://github.com/ape-byte/DouyinBarrageGrab) | C# | ~1.5k | 系统代理抓 WSS，支持直播伴侣/Chrome |
| [BarrageGrab](https://github.com/wushuaihua520/BarrageGrab) | C# | ~360 | 抖音/快手/TikTok/视频号/B站，无需代理 |
| [douyinLive](https://github.com/jwwsjlm/douyinLive) | Go | ~281 | 含 Dockerfile，2026-03 更新 |
| [UniBarrage](https://github.com/BarryWangQwQ/UniBarrage) | Go | ~85 | 统一多平台弹幕格式（抖音/B站/快手/斗鱼/虎牙），毫秒级延迟 |
| [TikTokLive](https://github.com/isaackogan/TikTokLive) | Python | ~1.4k | TikTok 国际版，支持 100+ 事件类型 |

### 直播录制 / 监控

| 项目 | 语言 | Stars | 说明 |
|------|------|-------|------|
| [DouyinLiveRecorder](https://github.com/ihmily/DouyinLiveRecorder) | Python | ~9.6k | 最活跃，支持 40+ 平台，可循环值守 |
| [StreamCap](https://github.com/ihmily/StreamCap) | Python | ~3.4k | 基于 FFmpeg，含 GUI，支持监控/定时/转码 |
| [stream-rec](https://github.com/stream-rec/stream-rec) | Kotlin | ~1.2k | 支持抖音/虎牙/斗鱼/Twitch，弹幕同步录制 |
| [DouyinLiveRecorder (LyzenX)](https://github.com/LyzenX/DouyinLiveRecorder) | Python | ~874 | 无需 Cookie，支持 GUI/命令行双模式 |

### 推流工具

| 项目 | 语言 | Stars | 说明 |
|------|------|-------|------|
| [douyin-rtmp](https://github.com/heplex/douyin-rtmp) | Python | ~304 | 一键获取抖音推流地址，有 GUI |
| [looplive](https://github.com/timerring/looplive) | Python | ~49 | 7×24 循环多平台同推，支持 CLI |

---

## 商业 / SaaS 工具

### 数据分析

**国内（抖音/快手/B站）**
- **蝉妈妈** — 直播 GMV 监控、带货达人排行、竞品分析
- **抖查查** — 实时热度/观众留存/GMV 趋势，账号全量数据
- **飞瓜数据** — 多平台数据监测，达人分析，热门商品挖掘

**TikTok 跨境**
- **FastMoss** — 商品/达人/店铺/广告七维度分析
- **Kalodata** — 实时销售追踪、选品趋势、竞品监控

### AI 数字人 / 无人直播

| 工具 | 说明 |
|------|------|
| 闪剪 | AI 数字人，7×24 不间断直播，1000+ 模板 |
| 创客兔 | 声音+形象克隆，本地部署，需 RTX 3060+ |
| 万兴播爆 (Virbo) | 文本转语音，直播实时互动，自动回复 |

### 多平台推流

| 工具 | 收费 | 说明 |
|------|------|------|
| OBS Studio | 免费开源 | 最主流，高度可定制 |
| StreamYard | $49/月起 | 浏览器端，多嘉宾连线，多平台同推 |
| Restream | $19/月起 | 30+ 平台同时推流 |

### 美颜 / 特效 SDK（面向开发者）

- **腾讯特效 SDK** — Web/移动端美颜特效，商业授权
- **相芯 FaceUnity** — 人脸美型，可通过声网 Beauty API 集成
- **ZEGO 即构美颜** — 全平台，按使用量计费

---

## 技术方案

### 弹幕 / 互动数据接入

#### 官方渠道（推荐）

| 平台 | 文档 | 门槛 | 说明 |
|------|------|------|------|
| **B站直播开放平台** | open-live.bilibili.com/document | 低，个人可申请 | 官方 WebSocket 长连接，直接推送弹幕/礼物/观看数，**最省心** |
| **抖音开放平台** | developer.open-douyin.com | 高，需企业资质 | 互动工具 API，Java/Node.js/Go SDK（v1.0.8），部分能力申请制 |
| **火山引擎 RTC** | — | 中，字节系生态 | 抖音同源技术，相比直接申请抖音开放平台门槛更低 |
| **快手开放平台** | open.kuaishou.com | 中 | 直播数据和互动 API，需申请 |

#### 非官方逆向方案

抖音直播弹幕通过 WSS 传输，数据采用 Protobuf 编码。**GitHub 上大量弹幕抓取项目停更的根本原因**：抖音会定期更新 `signature` 签名算法，逆向方案随版本更新频繁失效，维护成本极高。活跃项目（如 DouyinLiveWebFetcher）本质上是在持续追着抖音更新跑。

| 方案 | 说明 |
|------|------|
| JS 注入 + WebSocket Hook | 浏览器环境注入 JS 拦截数据帧，解包 Protobuf |
| 系统代理抓包 | 捕获直播伴侣或 Chrome 的 WSS 流量 |

> ⚠️ 非官方逆向方案违反平台服务条款，存在封号和法律风险，不建议用于商业产品。

#### TikTok 国际版

TikTokLive 库目前仍较活跃，背后有商业签名服务（[Euler Stream](https://eulerstream.com)）支撑，稳定性优于纯逆向方案，但仍属非官方。

### 推流协议对比

| 协议 | 延迟 | 适用场景 |
|------|------|----------|
| RTMP | 3–5s | 主播推流到服务器（最主流） |
| HLS | 6–30s | 大规模分发，自适应码率 |
| SRT | <2s | 专业广播，弱网最优 |
| WebRTC | <1s | 连麦、双向互动 |

### 云服务 SDK

| 厂商 | 产品 | 特点 |
|------|------|------|
| 腾讯云 | 云直播 CSS / 视立方 | 节点丰富，价格较低 |
| 阿里云 | 视频直播 | 阿里生态集成好 |
| 即构 ZEGO | 超低延迟直播 | 延迟 600ms，万人连麦 |
| 声网 Agora | 融合 CDN 直播 | 多 CDN 融合调度 |
| 火山引擎 | RTC SDK | 抖音同源技术，字节系生态 |

### FFmpeg 常用场景

```bash
# 录制 HLS 直播流
ffmpeg -i "https://example.com/live/stream.m3u8" -c copy output.mp4

# RTMP 推流
ffmpeg -re -i input.mp4 \
  -c:v libx264 -preset fast -b:v 3000k \
  -c:a aac -b:a 128k \
  -f flv rtmp://live.platform.com/live/your_stream_key
```

---

## 选型建议

| 需求场景 | 推荐方案 |
|----------|----------|
| 弹幕数据接入（稳定） | B站官方 WebSocket；抖音走开放平台或火山引擎 |
| 弹幕数据接入（快速验证） | UniBarrage（统一多平台）或 DouyinLiveWebFetcher（注意维护风险） |
| 直播录制存档 | DouyinLiveRecorder + FFmpeg |
| 多平台同推 | OBS Studio + Restream |
| 抖音带货数据 | 蝉妈妈 + 抖查查 |
| TikTok 跨境分析 | FastMoss + Kalodata |
| AI 无人直播 | 闪剪 / 创客兔 |
| 低延迟连麦 | WebRTC（即构/声网 RTC SDK） |
