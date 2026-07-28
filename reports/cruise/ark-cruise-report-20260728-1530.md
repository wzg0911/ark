# ARK 巡航报告 · 2026-07-28 15:30 CST

## 一、健康检查

| 检查项 | 结果 |
|--------|------|
| GitHub stars | 0（forks 0） |
| 新 issue/PR | 无新增（仅存量 spam Issue #1，待主人手动关闭） |
| 测试 | ✅ **248 passed, 3 skipped**（35.7s，覆盖并超过 9/9 基线） |
| 工作区 | 干净（daily_status.json 时间戳例行更新，已随本轮提交） |
| 远端同步 | ✅ 本轮提交后推送 |

## 二、本轮动作

### ✅ W32 诊断报告 5/5 产出：langchain-anthropic#39100（system 块 id 原样透传 → 400）

- **主题**：LangChain v1 标准内容块 API `create_text_block()` 给每个块铸造 `lc_<uuid4>` id。`langchain_anthropic._format_messages()` 对 human/assistant 文本块做字段收窄（剥离 id），**但 system 分支原样透传**——`lc_` id 直达 Anthropic API，换回 `400 "system.0.id: Extra inputs are not permitted"`。`get_num_tokens_from_messages()` 复用同一路径，token 计数同样失败。
- **ARK 实机验证：离线确定性复现**（langchain-anthropic 1.5.2 / langchain-core 1.5.1 / anthropic 0.120.0 / Python 3.11，独立 venv）：
  - 不打真实 API，直接检视 `_format_messages()` 出站 payload
  - 同批消息覆盖 system/human/assistant 三角色：**system 块 id 保留、role 块 id 被剥离**——不对称清洗铁证
  - 离线检视比打 API 更强：根因钉死在格式化层，完全确定性、可进 CI 回归
- **结构性观察**：「框架自铸元数据 → 泄漏到出站协议」。v1 内容块把 id 设为一等公民后，每个 provider 适配器的每个角色分支都必须显式过滤，漏一个分支就是 400。官方力推的迁移方向（v1 content_blocks）越早采用越先崩——与 #39047「官方指引即陷阱」同构。
- **ARK 映射**：`OutputValidator` 出站 payload wire-schema 白名单对账 + `InputGuard` internal 字段标记（`lc_` 前缀单点强制）+ OTel `block_source→formatter→rejected_field` 字段级留痕
- 新增 `docs/reports/ark-report-39100-20260728.html` + 复现脚本 `scripts/repros/repro_39100_system_block_id_leak.py`
- **社区现状**：2 位贡献者已认领（其一已有带测试的 fork 分支），修复方向共识（system 块套用同一收窄 helper）——ARK 差异化价值在「层级维度泄漏」的模式级定性与出站契约防御

### ✅ 缺陷模式索引 v2.4

- **新设 F9 · 出站契约不对称 / 内部元数据泄漏到 wire 协议**（首例 #39100）
- F9 与 F2 互为镜像：F2 泄漏在时间维度（本次参数污染下次调用），F9 泄漏在层级维度（内部元数据穿透 provider 协议层）；共同根因「边界缺强制清洗」
- 索引现状：**18 份报告 / 9 个缺陷族**

## 三、下一步工作状态

| 事项 | 状态 |
|------|------|
| **W32 诊断 5/5（#39100）** | ✅ **本轮完成 → 本周诊断目标达成**（当日五发：#39087 + #39099 + #39052 + #39047 + #39100） |
| W32 收尾 | 🟢 下轮候选：W32 周总结 / 对外叙事素材整理（"follow the official advice, crash immediately" 系列已有 #39047+#39100 双证据） |
| DEV.to 账号 + 构建日志 | 🟡 待主人授权外部账号 |
| GitHub Discussions 分发 | 🟡 待主人授权 |
| Issue #1 spam 关闭 | 🔴 需主人手动关闭+举报 |

## 四、结论

技术面全绿：248 测试通过、无新 issue/PR、已推送远端。本轮核心产出是 **W32 诊断 5/5 + 新设 F9 缺陷族**——**本周 5 份诊断目标提前达成**（周二即完成）。#39100 与 #39047 共同构成「官方推荐路径先崩」双证据链：一个是弃用警告推荐的选项 100% 崩溃，一个是力推的 v1 API 自铸元数据穿透协议层——这是 ARK 对外叙事的最强素材组合。索引升级至 v2.4（18 报告/9 族），F9 与 F2 的镜像关系（时间维度 vs 层级维度泄漏）为「边界强制清洗」这一 ARK 核心价值主张提供了双轴证据。

---

*生成时间：2026-07-28 15:30 CST | ARK Cruise Bot*
