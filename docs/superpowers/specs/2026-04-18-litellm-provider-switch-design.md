# LiteLLM 多 Provider 接入设计

## 背景

当前 `src/live/llm_client.py` 直接依赖 `vertexai.generative_models.GenerativeModel`,
锁死 Vertex AI。测试期希望走 Vercel AI Gateway,生产再切换到其他 provider
(Anthropic、OpenAI、自部署 Gemini 等)。

## 目标

- LLM 调用层与 provider 解耦,通过环境变量切换
- 测试链路接入 Vercel AI Gateway
- 不引入 LangChain;用 LiteLLM 做统一接口
- 现有 `DirectorAgent` / `LLMClient` 行为保持不变(prompt 不变、JSON 输出契约不变)

## 非目标

- TTS provider 切换(单独立项,见 tts-provider-design)
- Streaming 输出(directorAgent 当前不需要)
- 多模型 fallback(后置,先支持单 provider)

---

## 方案

### 依赖

```
litellm >= 1.50.0
```

包大小 ~30MB,纯 Python,无 native 依赖。

### 配置层

`src/api/settings.py` 新增:

```python
class Settings(BaseSettings):
    # 现有字段保留
    ...
    # 新增 LLM provider 配置
    llm_provider: str = "vertex_ai"          # vertex_ai | vercel | anthropic | openai
    llm_model: str = "gemini-2.5-flash"      # 模型名,与 provider 配套
    llm_api_base: str | None = None          # 自定义 endpoint(Vercel Gateway 用)
    llm_api_key: str | None = None           # 非 Vertex 的 provider 用
```

环境变量:

```bash
# 测试期(Vercel AI Gateway)
LLM_PROVIDER=vercel
LLM_MODEL=vercel/gemini-2.5-flash
LLM_API_BASE=https://gateway.ai.vercel.com/v1/your-project/...
LLM_API_KEY=<vercel-token>

# 生产(Vertex AI 直连)
LLM_PROVIDER=vertex_ai
LLM_MODEL=gemini-2.5-flash
GOOGLE_CLOUD_PROJECT=your-project

# 备选(Anthropic)
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
LLM_API_KEY=<anthropic-key>
```

### LLMClient 改造

`src/live/llm_client.py` 重写为 LiteLLM 调用:

```python
from litellm import completion

class LLMClient:
    def __init__(
        self,
        model: str,
        api_base: str | None = None,
        api_key: str | None = None,
        project: str | None = None,
    ) -> None:
        self._model = model
        self._api_base = api_base
        self._api_key = api_key
        self._vertex_project = project   # Vertex 走 ADC,不走 api_key

    def generate(self, prompt: str, system: str | None = None) -> str:
        """单轮生成,返回 raw text。"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.7,
            "response_format": {"type": "json_object"},   # LiteLLM 跨 provider 统一
        }
        if self._api_base:
            kwargs["api_base"] = self._api_base
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._vertex_project:
            kwargs["vertex_project"] = self._vertex_project
            kwargs["vertex_location"] = "us-central1"

        response = completion(**kwargs)
        return response.choices[0].message.content
```

### DirectorAgent 改动

`src/live/director_agent.py`:

- `llm_generate_fn` 签名不变(仍是 `Callable[[str], str]`)
- 在 `SessionManager` 装配时传入 `client.generate` 替代当前的 `model.generate_content`
- `parse_director_response` 不变

### SessionManager 装配改动

`src/live/session.py` 的 `_build_and_start`:

```python
from src.api.settings import get_settings
from src.live.llm_client import LLMClient

def _build_llm_client(mock: bool, project: str | None) -> LLMClient | None:
    if mock:
        return None
    settings = get_settings()
    return LLMClient(
        model=settings.llm_model,
        api_base=settings.llm_api_base,
        api_key=settings.llm_api_key,
        project=project or settings.google_cloud_project,
    )
```

mock 模式继续用固定回复,不走 LiteLLM。

### 旧 LLMClient.decide() 处理

当前 `LLMClient.decide()` 是早期 Orchestrator 用的,DirectorAgent 没用。

- 检查 grep 结果:`decide()` 仅在 `LLMClient` 自身和测试中出现
- 直接删除 `decide()` 方法和 `_SYSTEM_PROMPT`、`build_prompt`、`parse_response`
- 同步删除 `llm_client_test.py` 里 `decide` 相关 case

如果删除发现还有调用方,改为 deprecated 抛错,2 周后删。

---

## 测试

### 单元测试

`src/live/llm_client_test.py`:

```python
def test_generate_calls_litellm_with_vercel_config(monkeypatch):
    captured = {}
    def fake_completion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
        )
    monkeypatch.setattr("src.live.llm_client.completion", fake_completion)

    client = LLMClient(
        model="vercel/gemini-2.5-flash",
        api_base="https://gateway.ai.vercel.com/...",
        api_key="test-key",
    )
    result = client.generate("hello", system="you are a bot")

    assert result == '{"ok": true}'
    assert captured["model"] == "vercel/gemini-2.5-flash"
    assert captured["api_base"] == "https://gateway.ai.vercel.com/..."
    assert captured["api_key"] == "test-key"
    assert captured["messages"][0] == {"role": "system", "content": "you are a bot"}


def test_generate_passes_vertex_project_when_provided(monkeypatch):
    captured = {}
    monkeypatch.setattr("src.live.llm_client.completion",
                       lambda **kw: captured.update(kw) or SimpleNamespace(
                           choices=[SimpleNamespace(message=SimpleNamespace(content=""))]))

    client = LLMClient(model="vertex_ai/gemini-2.5-flash", project="my-proj")
    client.generate("hi")

    assert captured["vertex_project"] == "my-proj"
    assert captured["vertex_location"] == "us-central1"
```

### 集成测试(手动)

测试期用 Vercel AI Gateway:

```bash
LLM_PROVIDER=vercel \
LLM_MODEL=vercel/gemini-2.5-flash \
LLM_API_BASE=https://gateway.ai.vercel.com/v1/<project>/google-vertex-ai/v1 \
LLM_API_KEY=<token> \
uv run uvicorn src.api.main:app --reload --port 8000

curl -X POST http://localhost:8000/live/start \
  -H "Content-Type: application/json" \
  -d '{"mock": false}'
```

观察日志确认 LLM 调用走 Vercel Gateway。

---

## 影响面

| 文件 | 改动 |
|---|---|
| `pyproject.toml` | + `litellm>=1.50.0` |
| `src/api/settings.py` | + 4 个 LLM 配置字段 |
| `src/live/llm_client.py` | 重写 `generate()`,删 `decide()` 及相关 helpers |
| `src/live/llm_client_test.py` | 重写测试 |
| `src/live/session.py` | `_build_llm_client` 改用 settings |
| `.env.example` | 增加 LLM_* 示例 |

预计代码改动 ~150 行,测试 ~60 行。

---

## 风险与对策

| 风险 | 对策 |
|---|---|
| LiteLLM 对 Vertex AI 的 ADC 支持是否原生 | 已确认支持,通过 `vertex_project` + `vertex_location` 参数 |
| `response_format=json_object` 跨 provider 兼容性 | Vertex/OpenAI/Anthropic 均支持,Vercel Gateway 透传 |
| LiteLLM 内部缓存导致环境变量切换不生效 | 在 `LLMClient.__init__` 显式传参,不依赖全局 env |
| Vercel Gateway 限流 | 测试期可接受,生产切回 Vertex 直连 |

---

## 后置工作

- LiteLLM 的 fallback 机制(主 provider 挂了切备用):后置,稳定后再加
- LiteLLM 的成本追踪:可选,接入 LiteLLM proxy 后启用
- Streaming 输出:DirectorAgent 当前不需要,按需再加
