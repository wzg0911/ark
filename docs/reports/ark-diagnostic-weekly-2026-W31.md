# ARK Trust 诊断周报 · 2026年第31周

> 2026-07-21 ~ 2026-07-27 | ARK v0.8.0 Public Building Phase · Week 4

## 本周诊断成果（目标 5 份 · 达成 5/5 ✅）

| 诊断报告 | 仓库 | 问题类型 | ARK 组件 | 状态 |
|---------|------|---------|---------|------|
| #38708 | langchain-ai/langchain | ToolNode 不对等价并行 tool_call 去重 → 重复执行/重复扣费 | IdempotencyGuard | ✅ (1/5) |
| #35475 | langchain-ai/langchain | RunnableRetry.batch 部分成功/部分失败静默返回错位损坏输出 | OutputValidator | ✅ (2/5) |
| #38779 | langchain-ai/langchain (Anthropic) | bind_tools tool_choice 字典原地变异，per-call 参数泄漏 | InputGuard 不可变契约 | ✅ (3/5) |
| #38904 | langchain-core | 测试断言写错 + xfail 掩盖真实结构缺陷 | 契约测试 / OutputValidator | ✅ (4/5) |
| #38840 | langchain-ai/langchain (Perplexity) | extra_body 原地变异，per-call 参数永久沉淀泄漏 | InputGuard + per-call 隔离 | ✅ (5/5) ✅ |

---

## 案例详解

### 案例一 · #38708 — 等价并行 tool_call 重复执行
**问题：** LLM 常在单条 AIMessage 中一次性吐出多个完全相同的并行 tool_call（同名工具 + 等价参数，仅 JSON 键序不同）。LangChain 的 `ToolNode` 不做去重，把每个调用当作独立请求并行执行，导致**重复写入、重复 API 请求、重复扣费**，并向下游注入噪声状态。
**根因：** `AIMessage.tool_calls` 列表含 N 个等价调用 → ToolNode 逐条 invoke → 同一逻辑动作执行 N 次 → N 倍 API 成本 + N 次副作用 + 状态污染。
**ARK 修复：** `IdempotencyGuard` 以「工具名 + 规范化参数」为幂等键，等价调用第二次起直接命中缓存，副作用只发生一次。

### 案例二 · #35475 — 批处理静默返回错位损坏输出
**问题：** `RunnableRetry.batch` 在部分成功/部分失败场景下静默返回**错位（index 与结果不对应）**的损坏输出，调用方无从察觉。
**ARK 修复：** `OutputValidator` 对批处理结果强制 index/schema 不变式校验，错位即拦截，绝不把损坏结果当正常返回。

### 案例三 · #38779 — tool_choice 字典原地变异（Anthropic）
**问题：** `bind_tools` 路径原地篡改调用方传入的 `tool_choice`/参数字典，per-call 参数被永久写入实例状态，泄漏到后续所有请求。
**ARK 修复：** `InputGuard` 入参不可变契约（拷贝而非引用）+ `IdempotencyGuard` per-call 隔离 + OTel 参数漂移留痕。

### 案例四 · #38904 — 测试断言错误被 xfail 掩盖
**问题：** `test_stream_error_callback`（langchain-core）被标 `@pytest.mark.xfail(reason="failing due to a bug in the testing code")`。真实根因不是产品代码，而是**测试断言写错**：断言 `generations == []`，但 `generations` 是「每个 prompt 一个列表」的嵌套结构，空结果应为 `[[]]`。错误的 xfail 掩盖了对输出结构契约的验证。
**ARK 修复：** 用 `OutputValidator` 把「输出结构不变式」固化为运行时契约，而非靠人写对断言；xfail 不应成为结构缺陷的遮羞布。

### 案例五 · #38840 — Perplexity extra_body 原地变异
**问题：** `ChatPerplexity._to_responses_payload` 直接写入调用方传入的 `extra_body` 引用而非拷贝；叠加 `_generate` 的 `{**default, **kwargs}` 浅合并，per-call 参数（如 `search_mode`）永久沉淀进实例 `model_kwargs`，泄漏到后续所有请求。
**ARK 修复：** `InputGuard` 入参不可变契约 + per-call 参数隔离 + OTel 参数漂移留痕，把「靠人自觉别忘拷贝」升级为运行时可强制校验。

---

## W31 总结

**5 份诊断报告全部完成 ✅（Week4 诊断目标达成）**

### 🧬 核心发现：「可变状态原地篡改」缺陷族第三次复发
本周最重要的模式级发现——**#38779（Anthropic tool_choice）与 #38840（Perplexity extra_body）同族**，加上历史 #38659（Groq token_usage），构成同一「per-call 参数原地写入实例状态 → 静默泄漏到后续请求」形态的**第三次复发**。

| 复发点 | 载体 | 泄漏后果 |
|--------|------|---------|
| #38659 (历史) | Groq token_usage | 计量污染 |
| #38779 (W31) | Anthropic tool_choice 字典 | per-call 参数沉淀 |
| #38840 (W31) | Perplexity extra_body | search_mode 等参数永久泄漏 |

**结论：** 这不是偶发 bug，而是「配置即状态」的**系统性反模式**。ARK `InputGuard` 的入参不可变契约 + per-call 隔离 + OTel 参数漂移留痕，正是把这类「靠人自觉」的隐患升级为**运行时可强制校验**的信任层——ARK 的价值主张再次被真实缺陷验证。

**共同主题（W31）：** 框架在「可变状态 / 边界情况」上静默失败——重复执行、错位输出、参数泄漏、测试掩盖。ARK 是 Agent 与这些危险边界之间的唯一信任层。

---

*生成时间：2026-07-26 05:28 CST | ARK Cruise Bot | W31 完成（5/5）*
