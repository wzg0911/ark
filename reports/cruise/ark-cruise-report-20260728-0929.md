# ARK 巡航报告 2026-07-28 09:29 CST

## 一、状态总览

| 项目 | 状态 |
|------|------|
| Stars / Forks | 0 / 0（无变化） |
| Open Issues | 1（仅 Issue #1 spam，无新增） |
| Open PRs | 0 |
| 测试 | ✅ **248 passed, 3 skipped**（45.55s，全绿） |
| Git | 与 origin 同步，本轮推送 2 个提交 |

## 二、本轮动作

### 1. 仓库健康修复：.venv 误跟踪清除
- 发现 `.venv/` 有 **567 个文件（22MB）被 git 跟踪**（`.gitignore` 已含 `.venv/` 但文件早前已入库），导致 `git status` 数百行噪音且 **`git pull --rebase` 被 unstaged changes 阻塞**
- 执行 `git rm -r --cached .venv`，工作区恢复干净，pull/push 通路恢复正常

### 2. ✅ W32 诊断报告 2/5 产出：langchain-core#39099
- **主题**：args_schema 含未解析前向引用时，工具**静默以「零参数」schema 递交模型**（`{"properties": {}, "type": "object"}`），零日志零异常；模型据此发空参数调用后在校验层爆 ValidationError——advertised schema 与 enforced schema 自相矛盾
- **实机验证：5/5 完全复现**（langchain-core 1.5.1 / pydantic 2.13 / Python 3.11，独立 venv）：
  - `__pydantic_complete__ = False` ✅
  - `args = []`（零参数暴露）✅
  - openai_tool params 为空 schema ✅
  - `invoke({})` 抛 ValidationError（要求全部参数）✅
  - 对照组：同错误在签名一级是硬 `NameError` ✅（不一致性正是缺陷核心）
- **危害画像**：issue 报告者一个模块 13 个工具中 12 个受影响、数月无人察觉；LangGraph `InjectedState` 富类型场景高发
- **ARK 映射**：`InputGuard` 注册期 schema 完整性门禁（`__pydantic_complete__` + 签名/schema 参数数对账）+ `OutputValidator` 契约一致性不变式（advertised ⊇ enforced）+ OTel schema 指纹留痕
- 新增 `docs/reports/ark-report-39099-20260728.html`

### 3. 缺陷模式索引 v2.1
- #39099 归入 **F3 静默失败族 → 第 4 例**，且把该族从「运行时失败被吞」扩展到「**构建时降级被吞**」
- 索引现状：**15 份报告 / 7 个缺陷族**；F2（可变状态篡改）×3、F3（静默失败）×4 双复发族

## 三、下一步工作状态

| 事项 | 状态 |
|------|------|
| W32 诊断 2/5（#39099） | ✅ **本轮完成**（当日双发：早间 1/5 + 本轮 2/5） |
| W32 诊断 3/5 候选 | 🟢 已预筛：#39075（`__or__` 未文档化）偏弱；#39052（MMR lambda_mult 语义反转）优先级高，下轮验证 |
| 缺陷模式索引 v2.1 | ✅ 已更新（F3 → 4 例） |
| DEV.to 账号 + 构建日志 | 🟡 待主人授权外部账号 |
| GitHub Discussions 分发 | 🟡 待主人授权 |
| Issue #1 spam 关闭 | 🔴 需主人手动关闭+举报 |

## 四、结论

技术面健康：测试 248 全绿、无新 issue/PR。本轮完成两件实事：① 修复 .venv 误跟踪（567 文件/22MB，曾阻塞 rebase 通路）；② W32 诊断 2/5 落地——与早间 #39087 的「部分复现诚实披露」形成对照，#39099 是 **5/5 全要素确定性复现**，两份报告合起来展示 ARK 诊断范式对「概率性缺陷」与「确定性静默缺陷」的双覆盖。

---

*生成时间：2026-07-28 09:29 CST | ARK Cruise Bot*
