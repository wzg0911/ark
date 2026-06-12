# ARK × Langfuse 端到端演示 🛡🔭

**5 分钟看到 ARK 的可靠性事件流入 Langfuse** — 0 star 仓库的破圈演示。

## 🚀 快速开始

```bash
# 1. 启动 Langfuse + OTel Collector
docker compose up -d

# 2. 等待 Langfuse 启动 (约 30 秒)
docker compose logs -f langfuse-server | grep "ready"

# 3. 安装 ARK
pip install -e ../..

# 4. 运行演示
python app.py
```

打开浏览器:

- **Langfuse UI**: http://localhost:3000
  - 首次访问会要求创建账号 (本地演示账号,无邮件验证)
  - 创建 Project "ark-demo"
  - 进入 Traces 页面 → 看到 ARK 推送的事件

## 📊 你将看到什么

演示脚本会触发 4 大场景,每条场景都会在 Langfuse 中产生可视化 trace:

| 场景 | 事件类型 | Langfuse 表现 |
|------|----------|----------------|
| 🛡 幂等守护 | `ark.guardian.intercept` | trace 显示拦截 2 次重复支付 |
| ⚡ 熔断器 | `ark.circuit.open/close` | trace 显示 GPT-4 失败 3 次后切 Claude |
| 🔧 输出验证 | `ark.validation.fail/pass` | trace 显示拦截 3 个 Agent 幻觉 |
| 🔭 OTel 演示 | 全部 8 事件类型 | 1 个 trace 包含完整事件序列 |

## 🏗 架构

```
app.py
  │
  │  emit(ark.circuit.open, ...)
  │  emit(ark.guardian.intercept, ...)
  │  ...
  ▼
ARK OTelExporter
  │
  │  HTTP POST /v1/traces (OTLP/JSON)
  ▼
otel-collector (port 4318)
  │
  │  batch + resource processor
  ▼
Langfuse Server (port 3000)
  │
  ▼
Langfuse Web UI → 你看到的可视化 trace
```

## 🔧 自定义

### 推送到自己的 Langfuse 实例

修改 `docker-compose.yml` 中 `langfuse-server` 的 `NEXTAUTH_URL` 和 `otel-collector.yaml` 中的 `endpoint`。

### 推送到其他 OTLP 后端 (Jaeger / Tempo / Honeycomb)

修改 `otel-collector.yaml` 中的 `exporters` 部分,Langfuse exporter 替换为:

```yaml
exporters:
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true
```

### 触发真实 Agent 场景

把 `app.py` 中的 `demo_*` 函数嵌入你的 Agent:

```python
from ark import IdempotencyGuard
from ark.otel_exporter import get_otel_exporter

guard = IdempotencyGuard()
exporter = get_otel_exporter()  # 读取 ARK_OTEL_ENDPOINT

@guard.wrap
def my_agent_tool(query: str):
    # Guard 内部已自动 emit guardian.intercept / idempotency.miss
    return search_api(query)
```

只要设了 `ARK_OTEL_ENDPOINT` 环境变量,**零代码改动** 即可观测。

## 🧹 清理

```bash
docker compose down -v   # -v 删除数据卷
```

## 📜 License

MIT
