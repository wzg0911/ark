# ARK × F9 Self-Healing Agent — 5-Minute Demo

> 12-Factor Agents Factor 9: **"把错误压缩进上下文，让 LLM 自愈"**

## 🎯 这个 demo 展示什么

ARK F9 Error Compressor 的 4 个核心能力：

| 能力 | 解决的问题 | 演示 |
|------|-----------|------|
| `truncate_error()` | 5KB stack trace 喂给 LLM 会爆 context window | 把 5KB 压成 ~500 字符 + 末 3 行 stack + md5 hash |
| `should_retry()` | Auth 错误被傻乎乎重试 3 次，浪费 30s | 8 种 NON_RETRYABLE_TYPES 立即升级 |
| `with_retry()` | 网络抖动要手写指数退避 + fallback | 一行装饰器全搞定 |
| `error_to_llm_context()` | LLM 不知道哪里错了，改了又错 | 结构化 prompt：含历史尝试 + 自愈引导 + 升级路径 |

## 🚀 跑起来

```bash
# 1. 安装 ARK（开发模式）
cd ../..
pip install -e .

# 2. 跑 demo
cd examples/f9-self-healing
python app.py
```

## 📦 你会看到

```
🧬 F9 DEMO 1: truncate_error() — 把 5KB stack trace 压成 LLM 友好格式
  ✨ ARK F9 截断后 (~800 字符):
    {
      "type": "TransientAPIError",
      "message": "ConnectionResetError: HTTPSConnectionPool...truncated...",
      "stack_tail": ["...末 3 行 stack..."],
      "raw_hash": "a3b9c2d1"
    }

🧬 F9 DEMO 2: should_retry() — 不可重试错误立即升级
  🚫 立即升级  AuthError                → Authentication/Authorization error
  🚫 立即升级  ValidationError          → Schema/input validation error
  ✅ 可重试    TransientAPIError        → Network/transient error
  ✅ 可重试    RateLimitError           → Rate limit, backoff and retry

🧬 F9 DEMO 3: with_retry() — 重试+升级+fallback 一气呵成
  [Round 1] 50% 失败 → ARK 守护下自愈
  [Round 2] Auth 失败 → fallback 转人工
  [Round 3] 持续失败 → 达 max_attempts → 包装抛出（验证指数退避 1+2+4=7s）

🧬 F9 DEMO 4: error_to_llm_context() — 让 LLM 自己决定怎么修
  [ERROR CONTEXT] Tool `search_and_book_flight` has 3 failure(s)
  [ERROR] Tool `search_and_book_flight` failed (attempt 1)
  Type:    TransientAPIError
  Message: Connection reset
  💡 Hint: This is a repeat failure. Consider:
    - Different tool / approach
    - Different input parameters
  🚨 ESCALATE TO HUMAN: This tool has failed too many times.
```

## 🧬 基因来源

- **12-Factor Agents (HumanLayer)** Factor 9 — "把错误压缩进上下文"
- **Stripe API** — 错误响应 + 重试机制
- **AWS SDK** — 指数退避算法

## 🔗 相关

- [ARK F9 源码](../../src/ark/errors.py)
- [ARK F9 测试](../../tests/test_errors_f9.py)（27 个测试覆盖 8 个维度）
- [12-Factor Agents](https://github.com/humanlayer/12-factor-agents) — 原论文
