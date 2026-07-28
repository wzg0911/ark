# ARK 诊断缺陷模式索引 (Defect Pattern Index)

> 累积索引 · 覆盖 W29–W32（17 份诊断报告）| 更新：2026-07-28 13:35 CST | ARK Cruise Bot
>
> 目的：把散落在各周诊断报告中的真实 Agent 可靠性缺陷，按**缺陷族**归并成单一可导航索引——既是 ARK 价值主张的证据库，也是技术参考。每一条都源自主流框架（LangChain / LangGraph / CrewAI）的**真实 issue**，非虚构。

---

## 一、缺陷族总览（按 ARK 组件映射）

| # | 缺陷族 | 复发次数 | 核心 ARK 组件 | 相关报告 |
|---|--------|---------|--------------|---------|
| F1 | 重复执行 / 幂等缺失 | 2 | `IdempotencyGuard` | #34974, #38708 |
| F2 | **可变状态原地篡改 / 「配置即状态」** | **3** ⚠️ | `InputGuard`（入参不可变契约）+ OTel 漂移留痕 | #38779, #38840, #38989 |
| F3 | 静默失败 / 失败流伪装成功流 | **4** ⚠️ | `OutputValidator` + `CircuitBreaker` + `InputGuard` | #39039, #38892, #38893, #39099 |
| F4 | 测试掩盖 / 断言失效 | 2 | 测试即契约（xfail 审计 + 结构断言） | #38904, #35475 |
| F5 | 畸形输入 / DoS | 2 | `OutputValidator` Schema + `CircuitBreaker` | #38667, #38843 |
| F6 | 无限循环 / 递归耗尽 | 1 | `CircuitBreaker`（递归/循环上限） | #6731 |
| F7 | **非确定性一致性 / 批次时间基准漂移** | 1 | `OutputValidator`（完整性不变式）+ OTel 留痕 | #39087 |
| F8 | **语义反转 / 参数契约跨库漂移** | **2** ⚠️ | `OutputValidator` 行为不变式探针 + `InputGuard` 契约声明 | #39052, #39047 |

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
| langchain-core#39099 (W32) | args_schema 前向引用未解析时，工具静默以「零参数」schema 递交模型；同错误在签名一级却是硬 `NameError` | advertised ≠ enforced schema，12/13 工具空参数数月无人察觉；**ARK 实机 5/5 完全复现** |

**共性：** 框架在边界上「假装成功」。#39099 把该族从「运行时失败被吞」扩展到「**构建时降级被吞**」——schema 构建失败被静默折叠成语义完全不同的合法值（空 schema）。ARK 以终态不变式 + 注册期 schema 完整性门禁（`__pydantic_complete__` + 签名/schema 参数数对账）强制校验，让失败无法伪装成成功。

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

### F7 · 非确定性一致性 / 批次时间基准漂移 → `OutputValidator` 完整性不变式 🆕 (W32)

| Issue | 一句话 | 后果 |
|-------|--------|------|
| langchain-core#39087 | `InMemoryRecordManager.update()` 循环内逐文档取 `get_time()`，批次时间基准漂移越过 `index_start_dt` 分界线 | `cleanup="full"` 静默漏删，RAG 脏文档残留 |

**共性：** 批次级属性（时间基准）被实现成文档级属性，清理谓词的不变式被概率性破坏——测试机绿灯、生产高负载随机失守。**ARK 实机验证（诚实披露）：** 反模式在源码级确认属实（批次内 ~0.1ms 漂移），但 issue 声称的 num_deleted 漂移在本机 5/5 次均未触发——正因触发是非确定的，「多测几次」无用，唯有 `OutputValidator` 把「预期删除数=实际删除数」固化为运行时不变式 + OTel 留痕，才能让哪次触发哪次现形。

---

### F8 · 语义反转 / 参数契约跨库漂移 → `OutputValidator` 行为不变式探针 🆕 (W32)

| Issue | 一句话 | 后果 |
|-------|--------|------|
| langchain-qdrant#39052 | `lambda_mult` 被直接透传给 Qdrant 的 `diversity`，而 Qdrant 内部做 `lambda = 1.0 - diversity`，两层镜像约定叠加致 MMR 语义完全反转 | 用户设 1.0（纯相关）得到纯多样性，设 0.0 得到纯相关；跨 vectorstore 迁移时行为突变但代码零改动 |
| langchain-core#39047 (W32) | `index()` 对默认 sha1 发弃用警告并推荐 sha256/sha512/blake2b，但 `_calculate_hash()` 仅 sha1 分支做 uuid5 包装，其余返回裸 hexdigest | 遵循官方弃用建议 → UUID 校验型存储（Qdrant）当场 `ValueError` 崩溃；非校验型存储则 ID 全量漂移，增量索引静默重写/误删；**ARK 实机 4/4 矩阵复现** |

**共性：** 与 F3 的本质区别——F3 是「失败被伪装成成功」，F8 是**从头到尾没有失败**：每一步都是合法值 ∈ [0,1]、合法调用、合法返回 k 篇文档，唯独整体语义与用户意图精确相反。类型系统、schema 校验、异常监控全部盲区。**ARK 实机双向确定性复现：** 手工正交向量空间（3 近重复 + 2 正交），`:memory:` 本地 Qdrant，lambda=0.0 与 1.0 的实际输出均与「取反 lambda」的逐位预测完全一致——排除排序噪音解释，钉死语义反转。ARK 以已知构造探针数据集在集成时跑极值自检（lambda=1.0 结果⊆相关簇），让语义反转在接入当天现形。

**#39047 对本族的扩展：** 漂移引信可以是**框架自己的迁移指引**——「官方最佳实践」（弃用警告推荐的 encoder）与「能跑的配置」精确互斥，用户越守规矩越先崩溃。且崩溃（UUID 校验型存储）是幸运分支；非校验型存储下 ID 契约漂移完全静默，增量索引的去重锚点全部失效。ARK 对策：`InputGuard` ID 形状契约（uuid-required/free-form）写入前校验 + 迁移不变式对账（换 encoder 时重算既有样本 ID 并告警）。

---

## 三、方法论 · ARK 4P Framework

每份诊断遵循：**P1 Pinpoint**（精准定位错误模式）→ **P2 Probe**（探测根因）→ **P3 Prescribe**（映射 ARK 组件）→ **P4 Publish**（发布报告 + 归档知识库）。

## 四、核心叙事（对外分发用）

> 我们没有编造用例。我们逐周拆解 LangChain / LangGraph / CrewAI 里**真实存在**的可靠性缺陷。
> 17 份报告收敛成 8 个缺陷族，其中「可变状态原地篡改」三次复发、「静默失败」四次复发，
> 最新的 F8「语义反转/契约漂移」族已两次复发——它证明存在一类**永远不抛异常、永远返回合法值、却与用户意图精确相反**的缺陷，
> 甚至框架自己的弃用建议都可能是崩溃引信（#39047：官方推荐的三个 encoder 100% 崩溃）。
> 传统 APM 与类型系统对其完全免疫失效，唯有行为不变式探针可捕获。
> **ARK 就是 Agent 与这些危险边界之间的唯一信任层。**

---

*生成时间：2026-07-28 13:35 CST | ARK Cruise Bot | 累积索引 v2.3（W29–W32）*
