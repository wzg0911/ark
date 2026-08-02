# ARK Trust 诊断周报 · 2026年第30周

> 2026-07-24 ~ 2026-07-26 | ARK v0.8.0 Public Building Phase · Week 3

## 本周诊断成果（目标 5 份）

| 诊断报告 | 仓库 | 问题类型 | 状态 |
|---------|------|---------|------|
| #39039 | langchain-ai/langchain | Responses API 流式静默丢弃 failed/error 终止事件 | ✅ 已发布 (1/5) |
| #38989 | langchain-ai/langchain | usage_metadata_callback 异常退出后泄漏，token 计量静默污染 | ✅ 已发布 (2/5) |
| #38893 | langchain-ai/langchain | ModelRetryMiddleware 吞掉不可重试异常，转成"正常"AIMessage | ✅ 已发布 (3/5) |
| #38892 | langchain-ai/langchain | Fallbacks 把合法空流误判为失败，备胎静默替换主输出 | ✅ 已发布 (4/5) |
| #38667 | langchain-ai/langchain | BaseMessage.content_blocks KeyError DoS via 畸形 content_blocks | ✅ 已发布 (5/5) ✅ |

---

## 案例五：畸形 Content Blocks 触发 KeyError 拒绝服务

**问题来源：** langchain-ai/langchain#38667（2026-07-05 提交，bug/core/external 标签，4 评论）

**用户痛点（生产 DoS 事故）：**
Agent 接收外部输入（Webhook、用户消息、工具返回）时，若消息的 content_blocks 字段格式不完整，
访问 `.content_blocks` 属性直接抛出未捕获的 `KeyError`，导致 Agent 进程崩溃。
攻击者可通过构造畸形消息实现**拒绝服务攻击**。

**根因分析：**
```
block_translators/anthropic.py _convert_to_v1_from_anthropic_input()
→ 直接访问 block["source"]["data"]、block["source"]["url"] 等
→ 不校验 key 是否存在
→ 任何来源传入的畸形 content_block → KeyError
→ 未被 try/except 包裹 → 上游崩溃
```

**4 种触发路径：**
```python
# 路径1：image block 缺 "data"
HumanMessage(content=[{"type": "image", "source": {"type": "base64"}}])
# KeyError: 'data'

# 路径2：document block 缺 "url"
ToolMessage(content=[{"type": "document", "source": {"type": "url"}}])
# KeyError: 'url'

# 路径3：document block 缺 "file_id"
SystemMessage(content=[{"type": "document", "source": {"type": "file"}}])
# KeyError: 'file_id'

# 路径4：document block 缺 "data"
AIMessage(content=[{"type": "document", "source": {"type": "text"}}])
# KeyError: 'data'
```

**ARK Trust 修复方案：**
- `OutputValidator` — 在 Agent 接收外部消息时强制校验 content_blocks Schema，畸形数据在入口处被拦截，不进入业务逻辑
- `CircuitBreaker` — 外部输入源连续触发 KeyError 时熔断，快速失败而非进程崩溃
- `IdempotencyGuard` — 防止畸形消息被重复处理（攻击者重放畸形消息时，第一次拦截后，后续相同 key 直接命中缓存保护）

**报告链接：** `docs/reports/ark-report-38667-20260724.html`

---

## W30 总结

**5 份诊断报告全部完成 ✅**

| 报告编号 | 核心风险 | ARK 对应组件 |
|---------|---------|------------|
| #39039 | 失败流=成功流，静默截断 | OutputValidator + CircuitBreaker |
| #38989 | Token 计量静默泄漏 | OTel Bridge 留痕 |
| #38893 | 异常被吞，伪造成功消息 | OutputValidator 强制终态不变式 |
| #38892 | Fallback 静默替换合法输出 | OutputValidator + 幂等保证 |
| #38667 | KeyError DoS，畸形消息崩溃进程 | OutputValidator Schema + CircuitBreaker |

**共同主题：** 框架在"边界情况"上静默失败——ARK 是 Agent 与危险边界的唯一信任层。

---

*生成时间：2026-07-24 09:29 CST | ARK Cruise Bot | W30 完成*
