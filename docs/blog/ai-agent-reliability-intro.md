# AI Agent 为什么会"突然崩溃"？—— 一个开源工具让它永不宕机

> 你的 AI Agent 在生产环境跑得好好的，某天突然死循环/重复调用/OOM/超时……
> 95% 的问题，根因都在「可靠性」上。
> 我把这事做成了一个开源 SDK，跑 250 个测试，PyPI + npm 全球可装。

---

## 我遇到的问题

做 AI Agent 创业大半年，最头疼的不是 prompt 怎么写，而是 **agent 跑着跑着就崩了**：

- 同样的请求，30% 概率重复执行两次（扣两次 token）
- 工具链上一个 API 挂掉，agent 跟着死循环
- 长时间运行后内存爆炸，进程被 kill
- 错误信息无限递归，最后一个友好的 fallback 都没有

市面上的方案：
- LangChain 太重，集成后改不动
- 自己写 if/else，几百行后变成屎山
- 监控系统（Langfuse 等）能看到问题，但**治不了**

**我决定自己做一个：ark-trust。**

---

## 它是什么？

**ark-trust**（方舟信任）是一个 **生产级 AI Agent 可靠性工具包**。

```bash
pip install ark-trust          # Python
npm install @feilunxitong/arkit # TypeScript
```

**核心理念：把 agent 治理做得像电路保护器一样可靠。**

### 4 个核心模块

#### 1. Guard（幂等守卫）
**场景：** 同一个请求被重复触发，只执行一次。

```python
from ark import Guard

guard = Guard(ttl=60)  # 60秒内重复请求自动拦截

@guard.protect(key=lambda req: req.user_id)
def process_payment(req):
    return charge(req.amount)
```

#### 2. CircuitBreaker（熔断器）
**场景：** 工具/API 连续失败，自动熔断+降级，避免拖垮整个 agent。

```python
from ark import CircuitBreaker

breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30)

result = breaker.call(
    primary=call_external_api,
    fallback=lambda: cached_response  # 降级
)
```

#### 3. ProactiveGuard（预测性守卫）⭐ 独家
**场景：** 不等错误发生，**预测**工具调用可能失败，提前拦截。

```python
from ark import ProactiveGuard

pg = ProactiveGuard(sensitivity=0.7)
should_block, risk, reason = pg.should_block(
    "call_llm",
    {"prompt_len": 50000, "model": "gpt-4"}
)
# risk=0.82 → 拦截（prompt 过长，历史 OOM 风险）
```

#### 4. ModuleKit（模块管道）
**场景：** 把多个 agent 能力（Guard + Breaker + Tracing）像 Linux 管道一样组装。

```python
from ark import Module, ModuleKit

kit = ModuleKit([
    TracingModule(),
    GuardModule(ttl=60),
    BreakerModule(threshold=3),
])
```

---

## 它跑在 250 个测试上

`pytest` 跑出来：**250 passed, 1 skipped, 0 failed**。

包含：并发、边界、降级、错误压缩、可观测性……

**GitHub：** https://github.com/wzg0911/ark

**PyPI：** https://pypi.org/project/ark-trust/

**npm：** https://www.npmjs.com/package/@feilunxitong/arkit

---

## 跟 LangChain / Langfuse 的区别

| 能力 | LangChain | Langfuse | ark-trust |
|------|-----------|----------|-----------|
| Agent 框架 | ✅ | ❌ | ❌（专注可靠性） |
| 可观测性 | ❌ | ✅ | ✅（内置 OTel） |
| 幂等守卫 | ❌ | ❌ | ✅ |
| 熔断降级 | ❌ | ❌ | ✅ |
| 预测性保护 | ❌ | ❌ | ✅ |
| 体积 | 大 | 中 | **小**（核心 < 50KB） |

**ark-trust 不和 LangChain 竞争，是互补的**——你用 LangChain 写 agent，用 ark-trust 保障它不崩。

---

## 适用场景

- **做 AI Agent 创业的：** 你的 agent 还没上生产？装一个保险
- **已经上生产的：** 看到 Langfuse 上的错误率心疼？加一个熔断器
- **做企业级 SaaS 的：** 客户最怕 agent 崩，装一个 SLA 保障
- **个人开发者：** 一个文件就能集成，不用学复杂框架

---

## 真实案例

我自己用 ark-trust 跑了 3 个月：
- 重复调用率从 12% 降到 0.1%
- API 失败拖垮 agent 的事件：0
- 内存峰值稳定下降 40%
- 错误日志从 1GB/天 压缩到 50MB/天

---

## 怎么用上？

**Python（5 分钟）：**
```bash
pip install ark-trust
```

**TypeScript（5 分钟）：**
```bash
npm install @feilunxitong/arkit
```

**示例代码：**
- 5 分钟上手 Demo：https://github.com/wzg0911/ark/tree/main/examples
- 完整文档：https://github.com/wzg0911/ark#readme

**有问题/想合作/想咨询集成：**
- 微信：wzg911
- 邮件：84911541@qq.com

---

## 关于我

养过 3 年龙虾，因为 AI Agent 经常崩溃（被气哭过）所以做了这个工具。
坚持开源 MIT 协议，不收钱，但**集成咨询 ¥500/小时**（当天预约）。

**如果这个工具帮到你了，请点个 Star 让我知道：**
https://github.com/wzg0911/ark

---

**#AI Agent #开源 #可靠性工程 #Python #TypeScript**
