# ARK 巡航报告 — 2026-07-25 12:18 CST

## 一、状态总览

| 项目 | 状态 | 备注 |
|------|------|------|
| Stars / Forks | 0 / 0 | 无变化，冷启动瓶颈仍在 |
| Open Issues | 1 | #1 spam（TrustLoop），需主人手动关闭 |
| Open PRs | 0 | — |
| 测试通过率 | ✅ 248/248 passed, 3 skipped (25.7s) | 无失败、无回归 |
| Git | ✅ 已同步 origin/main（含昨日支付止血 c32a8c8） | 本次报告待推送 |
| 本日线索/付费 | 0/0 | daily_status.json 正常轮询 |

## 二、本次巡航结果

### 1. 测试：✅ 全绿（248/248 passed, 3 skipped）
所有测试套件通过，langfuse 相关 3 项 skip 正常。无回归。

### 2. Git 状态
- 拉取 origin 后同步至 c32a8c8（支付漏洞止血：claim 手动确认模式 + 手动发货脚本）
- 本地新增未跟踪备份 `docs/diagnose.html.bak.v16.20260725`（v16 页面备份，保留不入库）

### 3. GitHub
- Issue #1（TrustLoop spam）仍 open，需主人手动关闭
- 无新 issue / PR

## 三、本次推进：W31 诊断报告 2/5 — langchain#38779

**产出：** `docs/reports/ark-report-38779-20260725.html`

**议题：** `ChatAnthropic.bind_tools()` 静默变异调用方 `tool_choice` 字典
- 根因：`kwargs["tool_choice"] = tool_choice` 存引用后原地写入 `disable_parallel_tool_use` → 污染调用方对象
- 社区信号：5人独立收敛到同一行修复（`.copy()`），≥7个PR因"未分配"被自动关闭，issue开放15天
- 同型缺陷已扩散至 ChatPerplexity（#38840 extra_body 原地变异）→ 模式级"配置即状态"污染
- ARK 契合点：OutputValidator 配置不变式校验 + IdempotencyGuard 内容哈希暴露漂移 + OTel 变异事件留痕

## 四、W31 进度

| 目标 | 完成 | 状态 |
|------|------|------|
| W31 诊断报告（5份） | 2/5 | ✅ 本次+1（#38779） |
| 测试全绿 | ✅ | — |
| 巡航频率 | 正常 | — |

**W31 已完成：**
- ✅ #38892（RunnableWithFallbacks 空流静默污染）
- ✅ #38779（bind_tools tool_choice 字典变异）

## 五、持续阻塞项

| 阻塞项 | 影响 | 行动 |
|--------|------|------|
| 🔴 Issue #1 spam | GitHub活跃度 | 主人手动关闭 + 举报 |
| 🔴 Stars=0 | 冷启动 | 需发布分发内容（HN / Reddit / V2EX） |
| ⚪ Badge Service | 文档徽章 | 需 Vercel 重新部署 |

## 六、下一步

1. **立即：** 主人手动关闭 Issue #1
2. **本周内：** 发布 ARK Launch Kit（Hacker News Show HN / Reddit / V2EX）
3. **W31继续：** 剩余3份诊断报告，候选：#38904（测试代码bug）、#38840（Perplexity extra_body 变异，与本期同族可成系列）

---

**巡航时间：** 2026-07-25 12:18 CST
**巡航器：** ARK 7×24 巡航系统
