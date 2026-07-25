# ARK 诊断缺陷模式索引 (Defect Pattern Index)

> 累积索引 · 覆盖 W29–W31（13 份诊断报告）| 更新：2026-07-26 07:28 CST | ARK Cruise Bot
>
> 目的：把散落在各周诊断报告中的真实 Agent 可靠性缺陷，按**缺陷族**归并成单一可导航索引——既是 ARK 价值主张的证据库，也是技术参考。每一条都源自主流框架（LangChain / LangGraph / CrewAI）的**真实 issue**，非虚构。

---

## 一、缺陷族总览（按 ARK 组件映射）

| # | 缺陷族 | 复发次数 | 核心 ARK 组件 | 相关报告 |
|---|--------|---------|--------------|---------|
| F1 | 重复执行 / 幂等缺失 | 2 | `IdempotencyGuard` | #34974, #38708 |
| F2 | **可变状态原地篡改 / 「配置即状态」** | **3** ⚠️ | `InputGuard`（入参不可变契约）+ OTel 漂移留痕 | #38779, #38840, #38989 |
| F3 | 静默失败 / 失败流伪装成功流 | 3 | `OutputValidator` + `CircuitBreaker` | #39039, #38892, #38893 |
| F4 | 测试掩盖 / 断言失效 | 2 | 测试即契约（xfail 审计 + 结构断言） | #38904, #35475 |
| F5 | 畸形输入 / DoS | 2 | `OutputValidator` Schema + `CircuitBreaker` | #38667, #38843 |
| F6 | 无限循环 / 递归耗尽 | 1 | `CircuitBreaker`（递归/循环上限） | #6731 |

---

## 二、逐条索引

### F1 · 重复执行 / 幂等缺失 → `IdempotencyGuard`

| Issue | 一句话 | 后果 |
|-------|--------|------|
| langchain#34974 | HumanInTheLoopMiddleware + `ainvoke()` 高并发下重复调用同一工具 | 数据重复写入 |
| langchain#38708 | `ToolNode` 对等价并行 `tool_call`（仅键序不同）不去重 | N 倍 API 成本 + N 次副作用 |

**共性：** 框架无「幂等键」概念；朴素 `set()` 去重因键序被打乱而失效。ARK 以参数归一化幂等键在执行前拦截。

---

### F2 · 可变状态原地篡改 / 「配置即状态」→ `InputGuard` 不可变契约 ⚠️ 第三次复发

| Issue | 载体 | 泄漏后果 |
|-------|------|---------|
| (历史) Groq #38659 | `token_usage` | 计量污染 |
| langchain#38779 (W31) | Anthropic `tool_choice` 字典 | per-call 参数永久沉淀进实例 |
| langchain#38840 (W31) | Perplexity `extra_body` 字典 | `search_mode` 等参数泄漏到后续所有请求 |
| langchain#38989 (W30) | `get_usage_metadata_callback` 异常退出后累加器泄漏 | 后续调用 token 被静默累加进旧统计 |

**模式级发现（本索引头条）：** 「per-call 参数原地写入实例状态 → 静默泄漏到后续请求」已**第三次复发**。这不是偶发 bug，而是「配置即状态」的系统性反模式。ARK `InputGuard` 入参不可变契约 + per-call 隔离 + OTel 参数漂移留痕，把「靠人自觉别忘拷贝」升级为**运行时可强制校验**。

---

### F3 · 静默失败 / 失败流伪装成功流 → `OutputValidator` + `CircuitBreaker`

| Issue | 一句话 | 监管场景风险 |
|-------|--------|------------|
| langchain#39039 | Responses API 流式静默丢弃 `response.failed`/`error` 事件 | 失败流与成功流无法区分 |
| langchain#38892 | `RunnableWithFallbacks` 把合法空流误判为失败，备胎静默替换 | 静默数据污染（9 个 PR 卡关同因） |
| langchain#38893 | `ModelRetryMiddleware` 把「不可重试异常」吞成正常 `AIMessage` | 同一契约工具侧/模型侧行为相反 |

**共性：** 框架在边界上「假装成功」。ARK 以终态不变式强制校验，让失败无法伪装成成功。

---

### F4 · 测试掩盖 / 断言失效 → 测试即契约

| Issue | 一句话 | 后果 |
|-------|--------|------|
| langchain#38904 | `test_stream_error_callback` 被 `xfail` 长期掩盖 | 「流式错误回调」验证名存实亡 |
| langchain#35475 | `RunnableRetry.batch` 部分重试成功/部分失败时返回错位损坏输出 | 输出与输入错位，测试未覆盖 |

**共性：** 测试存在但不真正验证结构。ARK 主张结构级断言 + xfail 审计，防止「绿灯掩盖缺陷」。

---

### F5 · 畸形输入 / DoS → `OutputValidator` Schema + `CircuitBreaker`

| Issue | 一句话 | 后果 |
|-------|--------|------|
| langchain#38667 | `BaseMessage.content_blocks` 对畸形 block 抛未捕获 `KeyError` | 构造畸形消息即可 DoS 崩溃进程 |
| langchain#38843 | 链接类工具调用在畸形/边界输入下失败 | 工具调用静默失败 |

**共性：** 外部输入未在入口校验。ARK 在 Agent 接收外部消息时强制 Schema 校验 + 熔断，畸形数据入口即拦截。

---

### F6 · 无限循环 / 递归耗尽 → `CircuitBreaker`

| Issue | 一句话 | 后果 |
|-------|--------|------|
| CrewAI/langgraph#6731 | Text-to-SQL Agent 无限循环直到递归上限 | 资源耗尽 / 成本失控 |

**共性：** 缺乏循环/递归级熔断。ARK `CircuitBreaker` 提供循环上限与快速失败。

---

## 三、方法论 · ARK 4P Framework

每份诊断遵循：**P1 Pinpoint**（精准定位错误模式）→ **P2 Probe**（探测根因）→ **P3 Prescribe**（映射 ARK 组件）→ **P4 Publish**（发布报告 + 归档知识库）。

## 四、核心叙事（对外分发用）

> 我们没有编造用例。我们逐周拆解 LangChain / LangGraph / CrewAI 里**真实存在**的可靠性缺陷。
> 13 份报告收敛成 6 个缺陷族，其中「可变状态原地篡改」已**第三次复发**——
> 这证明：Agent 框架的可靠性问题不是偶发 bug，而是系统性反模式。
> **ARK 就是 Agent 与这些危险边界之间的唯一信任层。**

---

*生成时间：2026-07-26 07:28 CST | ARK Cruise Bot | 累积索引 v1（W29–W31）*
