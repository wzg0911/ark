# ARK Trust 诊断周报 · 2026年第30周

> 2026-07-24 ~ 2026-07-26 | ARK v0.8.0 Public Building Phase · Week 3

## 本周诊断成果（目标 5 份）

| 诊断报告 | 仓库 | 问题类型 | 状态 |
|---------|------|---------|------|
| #39039 | langchain-ai/langchain | Responses API 流式静默丢弃 failed/error 终止事件 | ✅ 已发布 (1/5) |
| #38989 | langchain-ai/langchain | usage_metadata_callback 异常退出后泄漏，token 计量静默污染 | ✅ 已发布 (2/5) |
| #38893 | langchain-ai/langchain | ModelRetryMiddleware 吞掉不可重试异常，转成"正常"AIMessage | ✅ 已发布 (3/5) |

---

## 本周首发案例：失败流与成功流不可区分

**问题来源：** langchain-ai/langchain#39039（2026-07-23 提交，bug/openai 标签）

**用户痛点（生产事故实录）：**
LangGraph Agent 流式生成中途 OpenAI 后端杀掉了流，`ainvoke` 返回一条"正常"的
AIMessage（半截 reasoning、无正文），graph 把它当最终答案，用户收到静默。
**没有异常、没有日志，排查耗时 2 天。**

**根因分析：**
```
Responses API 4 种终止事件 → 转换器只处理 completed/incomplete
→ response.failed / error 掉入 else 被静默丢弃（error payload 一起丢）
→ 无终止事件的死流也按正常结束处理
→ 失败流 = 成功流，下游零自救机会
```

**ARK Trust 修复方案：**
- `OutputValidator` — 守住"输出必须携带明确终态"的不变式，status 缺失 1 秒暴露
- `CircuitBreaker` — 上游连续死流时熔断快速失败，防止损坏输出持续流向用户
- OTel Bridge — `ark.validation.fail` 事件进入 Langfuse/Jaeger，静默失败留痕可审计

**报告链接：** `docs/reports/ark-report-39039-20260724.html`

---

## 案例二：计量数据静默污染（财务级风险）

**问题来源：** langchain-ai/langchain#38989（2026-07-21 提交，bug/core 标签）

**用户痛点：**
`get_usage_metadata_callback` 的清理逻辑没有 try/finally 保护——with 块内一旦抛异常，
回调保持全局注册，**块外的所有模型调用继续累加进旧统计**（复现打印 6 而非 3）。
没有报错、没有日志，只有悄悄错掉的 token 计量。对按 token 计费/配额限流的产品是财务级风险。

**根因分析：**
```
contextmanager yield 裸奔（无 try/finally）
→ 块内 raise 时清理语句被跳过
→ ContextVar 泄漏，回调永久注册
→ 后续调用 token 全部污染进旧统计
→ 同库 tracers.context 的邻居写法正确，属漏改
```

**ARK Trust 修复方案：**
- `OutputValidator` — 守住"单次操作 token 用量必须在合理区间"的计量不变式，污染即超界即报错
- OTel Bridge — ARK 事件流独立于 LangChain ContextVar，天然免疫本 bug，作为第二信源对账
- 上游 patch（issue 作者已提供）解决泄漏本身，边界校验仍是长期防线

**报告链接：** `docs/reports/ark-report-38989-20260724.html`

---

## 案例三：异常契约双侧不一致——错误被伪装成正常回答

**问题来源：** langchain-ai/langchain#38893（2026-07-16 提交，bug/langchain 标签，8 评论）

**用户痛点：**
用户配置 `retry_on=(ValueError,)` 显式声明"其它异常我自己处理"，但 `ModelRetryMiddleware`
把不匹配的 TypeError 吞掉，转成一条 `"Model call failed after 1 attempt..."` 的 AIMessage，
graph 当作模型回答继续跑。**工具侧（#38845 修复后）同样配置会正确抛出**——同一契约双侧行为相反。

**根因分析：**
```
#38845 只改了 tool_retry.py（不可重试 → bare raise）
→ #38884 基于新行为写死文档契约
→ model_retry.py sync/async 两条路径漏改（旧代码+旧注释原样残留）
→ 不可重试异常进 _handle_failure → on_failure="continue" 转成 AIMessage
→ 异常降级为聊天文本，所有基于异常的防御失效
```

**ARK Trust 修复方案：**
- `OutputValidator` — 守住"输出必须是真实回答"的不变式，错误文案 AIMessage 立即 ValidationError
- `CircuitBreaker` — 连续伪回答触发熔断，阻止错误消息洪流污染会话与下游
- 上游一行修复（对齐 tool_retry.py 的 raise）即可对齐契约

**报告链接：** `docs/reports/ark-report-38893-20260724.html`

---

## 诊断方法论 · ARK 4P Framework

- **P1 Pinpoint** — 提取错误模式（重复执行？静默失败？输出未校验？）
- **P2 Probe** — 定位根因（issue 历史 / bug pattern / 边界条件）
- **P3 Prescribe** — 映射 ARK 组件（IdempotencyGuard / CircuitBreaker / OutputValidator）
- **P4 Publish** — 报告发布 + 归档知识库

---

*生成时间：2026-07-24 01:29 CST · ARK 建造巡航自动生成*
