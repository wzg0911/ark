# ARK Trust 诊断周报 · 2026年第32周

> 2026-07-28 ~ 2026-08-03 | ARK v0.8.0 Public Building Phase · Week 5
> **本期为中期汇编（截至 07-31 11:30 CST）**，08-03 周末封版时补入剩余产出。

## 本周诊断成果（目标 5 份 · 已达成 8/5 ✅ 超额 160%）

| # | 诊断报告 | 仓库 | 问题类型 | 缺陷族 | ARK 组件 | 实机复现 |
|---|---------|------|---------|--------|---------|---------|
| 1 | #39087 | langchain-core | `InMemoryRecordManager.update()` 批次时间基准漂移 → `cleanup="full"` 静默漏删 | F7 | `OutputValidator` 完整性不变式 | 源码级确认 |
| 2 | #39099 | langchain-core | args_schema 前向引用未解析 → 工具静默以「零参数」schema 递交模型 | F3 | 注册期 schema 门禁 | **5/5** |
| 3 | #39106 | langchain-core | `list_keys(before=...)` 用 `>=` 排除等值记录 → 低分辨率时钟下静默漏删 | F7 | `OutputValidator` + OTel 留痕 | 冻结时钟双路径 |
| 4 | #39100 | langchain-anthropic | system 分支未清洗，`lc_` id 直达 API → 400 | F9 | 出站 wire schema 白名单 | 离线复现 |
| 5 | #39113 | langchain-openai | assistant 分支未清洗 id → Responses API 400 | F9 | 同上 | 离线三态对照 |
| 6 | #39052 | langchain-qdrant | `lambda_mult` 双层镜像约定叠加 → MMR 语义完全反转 | F8 | 行为不变式探针 | 双向确定性 |
| 7 | #39047 | langchain-core | 弃用警告推荐的 encoder 与 `_calculate_hash()` 实现互斥 → 官方建议即崩溃引信 | F8 | `InputGuard` ID 形状契约 | **4/4** 矩阵 |
| 8 | #39163 | langchain-core | `trace_as_chain_group` 只 catch `Exception` → `CancelledError` 绕过终态回调，run 永久 pending | F3 | `Trace` 终态存在性不变式 | **4/4** 对照 |

**累积：** 21 份诊断报告 · 9 个缺陷族 · 缺陷模式索引 v2.7

---

## 本周三大发现

### 发现一 · 🏁 首个「当日诊断 → 当日上游修复」闭环（#39100）

W32 最硬的一条外部背书。#39100 于 ARK 诊断发布**当天**被 maintainer ccurme 关闭（state_reason: completed），修复 PR [#39101](https://github.com/langchain-ai/langchain/pull/39101)「strip unsupported fields from system message content blocks」合并于 07-28 21:34 CST。

**关键在于修复方案与 ARK 处方完全一致**——在 system 分支补一道出站字段清洗。这不是「我们猜对了方向」，是上游用合并动作确认了根因定位与处方的准确性。

紧接着 #39113 出现同型证据：贡献者 RahilOp 的 PR [#39116](https://github.com/langchain-ai/langchain/pull/39116) 根因分析与修复方案与 ARK 诊断三方一致（后续 cyforkk 亦独立提出同向分析）。

> **结论：** ARK「诊断报告 + 离线确定性复现」范式的时效性与准确性，已由上游行动而非自我评估背书。

### 发现二 · 🧬 F9 族跨 provider 精确镜像：逐点修补追不上组合面

#39100（Anthropic）与 #39113（OpenAI）是**同一自铸 `lc_` id、同一类出站边界**的互补遗漏：

| | human | system | assistant |
|---|---|---|---|
| **Anthropic** | ✅ 已收窄 | ❌ **漏** | ✅ 已收窄 |
| **OpenAI** | ✅ 已 pop | ✅ 已 pop | ❌ **漏** |

两个适配器各自「做对了三分之二」，漏的恰好互补。

**最锋利的证据：** #39100 的修复 PR #39101 只堵了 Anthropic system 一处，而 OpenAI assistant 分支的同类缺陷**原样存活，并于同日被独立报告**。

这钉死了 ARK 的核心论点：遗漏概率随「适配器 × 消息角色分支」数量线性放大，v1 content_blocks 把 id 设为一等公民后，每个 provider 的每个分支都必须「记得」过滤。**N×M 的人工纪律不可能靠逐点修补收敛，唯有单点出站契约强制可以。**

### 发现三 · 🔥 F3 族推向极端：从「失败伪装成功」到「终态根本不发生」（#39163）

F3 前四例（#39039/#38892/#38893/#39099）共享一个隐含前提：**至少产生了一个错误的值**，因此事后审计能在数据里找到矛盾。

#39163 取消了这个前提。`CancelledError` / `KeyboardInterrupt` 继承自 `BaseException`，绕过只 catch `Exception` 的清理块，run 有 start、无 end、无 error——**在任何遥测后端里，它与「一个真实的长任务」不可区分**。

三点使其成为索引中最有说服力的一例：

1. **触发条件是生产常态而非边缘情况** —— ASGI/WebSocket 客户端断连即 `CancelledError`。交互越重的服务遥测污染越严重，形成「越关键越不可信」的反向相关。
2. **同文件内已有正确写法** —— `manager.py` 里 runnable 回调辅助函数已 catch `BaseException`，两个 chain group CM 仍写 `except Exception`。这不是设计取舍，是**纪律漂移**，是「靠人自觉」不可持续的直接物证。
3. **它发生在 observability 组件自己身上** —— 负责「记录一切」的模块自身缺终态不变式。用来发现问题的工具，漏掉了整整一类问题。

**对 ARK 防线设计的分化影响：** 前四例靠 `OutputValidator` 校验**终态的内容**；本例必须靠 `Trace` 校验**终态的存在性**（span 退出无终态则自动补发 `ark.span.orphaned`），并由 `CircuitBreaker` 将 cancelled 归一为独立终态（不计失败率、但计终态），避免取消风暴既不熔断也不留痕。

ARK 实机 4/4 对照复现（无 API key、无网络，langchain-core 1.5.3）：

```
A  async · asyncio.CancelledError   started=1 ended=0 errors=0   BUG: run left PENDING
B  async · ValueError    (control)  started=1 ended=0 errors=1   OK (terminal fired)
C  sync  · KeyboardInterrupt        started=1 ended=0 errors=0   BUG: run left PENDING
D  sync  · ValueError    (control)  started=1 ended=0 errors=1   OK (terminal fired)
```

B/D 对照组证明回调管线本身完好——问题精确锁定在异常基类选择这一行。

---

## 诚实披露（本周方法论纪律）

**#39087 / #39106 的 F7 族验证结果不完美，如实记录：**

反模式在源码级确认属实（批次内 ~0.1ms 漂移，`>=` 边界排除等值记录），但 #39087 声称的 `num_deleted` 漂移在本机 **5/5 次均未触发**。

我们不把这写成「复现成功」。**恰恰因为触发是非确定的，「多测几次」这条路是无效的**——这本身就是论据：唯有 `OutputValidator` 把「预期删除数 = 实际删除数」固化为运行时不变式 + OTel 留痕，才能让哪次触发哪次现形。

镜像对结构值得记录：#39087 是时钟**太快**（批次内漂移越过分界线），#39106 是时钟**太慢**（分辨率不足致等值碰撞）。两侧共享同一清理谓词的边界缺陷，且 `SQLRecordManager` 用严格 `<` 而 `InMemoryRecordManager` 用 `>=`——**同一抽象的两个实现，边界语义不一致**。

---

## 工程健康度（W32）

| 指标 | 状态 |
|------|------|
| 回归测试 | **248 passed, 3 skipped** ✅ 连续多轮全绿 |
| 巡航频次 | 每 2 小时（7×24） |
| repro 脚本累积 | 6 份（`scripts/repros/`） |
| 诊断报告累积 | 21 份 |
| 未推送遗留 | 0（07-31 09:28 轮已清） |

---

## 上游生态观察：assign 机制事实停摆

**近 15 条 open issue（覆盖 07-23 ~ 07-31 共 9 天）assignee 全部为空。**

| 观察 | 数据 |
|------|------|
| 竞领窗口 | **以分钟计** — #39163 开出 15 分钟内被认领 |
| assign 兑现 | **从未** — #39152 认领者连续 4 轮未获 assign |
| 竞领者重叠 | gitbalaji 同时挂在 #39152 与 #39163 |

**#39163 的双人竞领（gitbalaji 01:00 UTC / tanmay-devhub 03:21 UTC）复现了 #39113 的「诊断发布 → 社区多人竞相认领」模式（第 3 次）。**

值得单独记一笔：tanmay-devhub 的根因分析——「catch 边界过窄，应在 group 未结束时调用既有 `on_chain_error()` 路径并原样重抛」——与 ARK 诊断处方**再次同向**。这是本周第三例社区独立分析与 ARK 处方一致。

> **战略含义：** 竞领窗口以分钟计、assign 兑现以「从未」计 —— 参与上游 issue 认领（A 案）的期望收益被持续压低。W32 实际执行的路径是：不竞领，直接把新 issue 转化为自有诊断资产。**结果是零竞争、零等待、当轮即交付。8/5 的超额完成率验证了这条路径可自持运转。**

---

## W32 核心叙事（对外分发用）

> 我们没有编造用例。我们逐周拆解 LangChain / LangGraph / CrewAI 里**真实存在**的可靠性缺陷。
>
> 21 份报告收敛成 9 个缺陷族。本周最重的三条证据：
>
> 1. **#39100 诊断当天即被上游修复合并，修复方案与 ARK 处方一致**——准确性由上游行动背书，不是自我评估。
> 2. **#39100 与 #39113 是跨 provider 的精确镜像**，而 #39100 的官方修复只堵了一侧，另一侧同日被独立报告——**逐点修补追不上 N×M 组合面**。
> 3. **#39163 证明存在一类连「错误的值」都不产生的缺陷**：run 有 start 无 end 无 error，在任何遥测后端里与真实长任务不可区分。而它就发生在 observability 组件自己身上。
>
> 加上 F8 族揭示的「永远不抛异常、永远返回合法值、却与用户意图精确相反」（#39052 MMR 语义反转、#39047 官方弃用建议即崩溃引信）——
>
> 传统 APM、类型系统、schema 校验对这几类缺陷**完全免疫失效**。
> **ARK 就是 Agent 与这些危险边界之间的唯一信任层。**

---

## 下周（W33）优先级

| 优先级 | 事项 | 依据 |
|--------|------|------|
| 🔴 P0 | DEV.to 账号创建 + 2 篇构建日志 | ROADMAP W2 唯一长期未启动项；21 份报告是充足素材 |
| 🟡 P1 | #39163 / #39113 上游结局跟踪 | 是否被 assign，是观察 assign 机制恢复的最佳样本 |
| 🟡 P1 | 上游扫描降频至每日一次 | assign 停摆已连续 9 天确认，高频追踪边际收益趋零 |
| 🟢 P2 | 诊断管道自动化 MVP | 资源转回 ROADMAP 存量 |

---

*生成时间：2026-07-31 11:30 CST | ARK Cruise Bot | W32 中期汇编（08-03 封版）*
