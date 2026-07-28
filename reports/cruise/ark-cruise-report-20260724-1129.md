# ARK 建造巡航报告 · 2026-07-24 11:29 CST

## 一、状态总览

| 项目 | 状态 | 备注 |
|------|------|------|
| Stars | 0 | 等待公开分发 |
| Forks | 0 | — |
| Open Issues | 1 | #1 spam（TrustLoop），需手动关闭 |
| Open PRs | 0 | — |
| 测试通过率 | ✅ 248/248 passed, 3 skipped (50s) | 无失败、无回归 |
| Git | ✅ 8b4f023 → 已推送 | — |
| 本日线索/付费 | 0/0 | 正常 |

## 二、W31 启动 · 首份诊断报告 #38892

**问题：** `RunnableWithFallbacks.stream()` 用 `next(stream)` 偷窥第一个chunk——当primary合法返回零chunk时，
`StopIteration` 被 PEP 479 转为 `RuntimeError`，再被 `exceptions_to_handle=(Exception,)` 捕获，导致：
1. **fallback静默替换正确的空结果**（调用方无法发现）
2. **无fallback时抛RuntimeError**（把正常空流误报为bug）

**监管场景风险极高：** 在合规审查/数据分析中，"该步骤正确返回空结果"本身就是重要发现（如"本协议无排除条款"）。
空结果被静默替换改变了流水线的语义，且fallback内容本身合理——调用方无法区分。

**社区共识：** 9个PR全部被自动关闭（无人认领），但4位独立研究者（@sergioperezcheco、@ErenAta16、@truongsontung、@PiedPiper911）全部收敛到同一修复：
`next(stream, sentinel)` 哨兵值法，完美符合bug本质。

**ARK修复方案：**
- `OutputValidator` — 强制 `fallback` 触发时携带 `_producer` 字段，打破静默替换
- `CircuitBreaker` — 空流率异常高时触发熔断
- `IdempotencyGuard` — 幂等保护暴露真实primary空流频率
- OTel Bridge — `ark.fallback.trigger` 事件全链路追踪

**报告：** `docs/reports/ark-report-38892-20260724.html`

## 三、GitHub最新Issue扫描（W31储备）

| Issue | 标签 | 评论数 | 状态 | 优先级 |
|-------|------|--------|------|--------|
| #38892 | bug/core | 13条 | 9个PR全卡关 | ⭐⭐⭐ W31-1 ✅ |
| #38904 | bug/core | 8条 | 测试代码bug，6人争抢 | 待评估 |
| #38779 | bug/anthropic | 7条 | tool_choice字典mutation | 待评估 |
| #38869 | bug/openai | 7条 | Responses API dict mutation | 待评估 |
| #38977 | bug/anthropic | 4条 | streaming display=omitted replay失败 | 待评估 |

## 四、持续异常（主人阻塞项）

1. 🔴 Badge Service 宕机 → 需 Vercel Dashboard 重新部署
2. 🔴 Issue #1 spam → 需手动关闭 + 举报
3. ⚪ Star=0 停滞 → 需 DEV.to 授权 + 公开分发

## 五、下一步

- W31 继续扫描高质量新 issue（目标 5 份）
- 下一优先：#38904（测试代码bug，多人争抢，可作为"高质量诊断"展示）
- 等待主人授权：DEV.to 账号创建 + 构建日志发布
