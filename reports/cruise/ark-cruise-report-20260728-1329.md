# ARK 巡航报告 2026-07-28 13:29

## 一、健康检查

| 检查项 | 结果 |
|--------|------|
| 测试 | ✅ **248 passed, 3 skipped**（32.9s，全绿） |
| GitHub stars/forks | 0 / 0（无变化） |
| 新 issue/PR | 无新增（仅存量 spam issue #1，待主人手动关闭；PR 0） |
| 工作区 | 干净（daily_status.json 时间戳例行更新，已随本轮提交） |
| 远端同步 | ✅ 已推送 d76964d..7235a6b |

## 二、本轮动作

### ✅ W32 诊断报告 4/5 产出：langchain-core#39047（弃用警告推荐的 key_encoder 100% 崩溃）

- **主题**：`index()` 对默认 `key_encoder="sha1"` 发 UserWarning，官方建议切换到 `blake2b/sha256/sha512`——但 `_calculate_hash()` 只有 sha1 分支做 `uuid.uuid5()` 包装，其余三个返回 64/128 位裸 hexdigest。**遵循框架自己的弃用建议，会让所有 UUID 校验型 vectorstore（Qdrant）当场 `ValueError` 崩溃**。
- **ARK 实机验证：4/4 全矩阵复现**（langchain-core 1.5.1 / langchain-qdrant 1.1.0 / qdrant-client 1.18.0 / Python 3.11，复用 #39052 独立 venv）：
  - 同一文档、同一 `:memory:` Qdrant，仅变更 key_encoder：sha1 ✅ 唯一能跑；sha256/sha512/blake2b 全部 `Point id ... is not a valid UUID`
  - 矩阵式复现证明是「除 sha1 外全部缺 uuid5 包装」的结构性缺陷，与数据内容无关
- **超越原 issue 的分析增量**：崩溃是幸运分支——非 UUID 校验型存储（Chroma/FAISS）下切换 encoder 会让同一批文档拿到全新 ID，增量索引去重锚点全部静默失效 → 全量重写/误删。
- **ARK 映射**：`InputGuard` ID 形状契约（uuid-required/free-form）写入前校验 + `OutputValidator` 迁移不变式对账 + OTel `key_encoder→id_shape→store_contract` 留痕
- 新增 `docs/reports/ark-report-39047-20260728.html` + 复现脚本 `scripts/repros/repro_39047_key_encoder_uuid_break.py`
- **社区现状**：4 位贡献者排队认领、修复方向已共识（全算法 uuid5 包装）——ARK 差异化价值在「官方指引即陷阱 + 静默 ID 漂移」的防御视角

### ✅ 缺陷模式索引 v2.3

- **F8 · 语义反转 / 参数契约跨库漂移 → 第 2 例复发**（#39052 + #39047，同为 langchain↔qdrant 接缝）
- F8 边界从「参数语义」扩展到「迁移指引」：官方最佳实践与能跑的配置精确互斥，用户越守规矩越先崩溃
- 索引现状：**17 份报告 / 8 个缺陷族**

## 三、下一步工作状态

| 事项 | 状态 |
|------|------|
| W32 诊断 4/5（#39047） | ✅ **本轮完成**（当日四发：#39087 + #39099 + #39052 + #39047） |
| W32 诊断 5/5 候选 | 🟢 待下轮预筛（候选：#39100 ChatAnthropic system block id / #39075 Runnable.__or__） |
| 缺陷模式索引 v2.3（F8 第 2 例） | ✅ 已更新 |
| DEV.to 账号 + 构建日志 | 🟡 待主人授权外部账号 |
| GitHub Discussions 分发 | 🟡 待主人授权 |
| Issue #1 spam 关闭 | 🔴 需主人手动关闭+举报 |

## 四、结论

技术面全绿：248 测试通过、无新 issue/PR、已推送远端。本轮核心产出是 **W32 诊断 4/5 + F8 族第 2 例**——#39047 与 #39052 同族且同一接缝（langchain↔qdrant），二连击把 F8 从「孤例」升级为「复发模式」，且引信升级为框架自己的弃用警告：**官方推荐的三个选项 100% 崩溃**。这是对外叙事的高传播素材（"follow the official advice, crash immediately"）。W32 诊断进度 4/5，当日四发，大幅超前周计划。

---

*生成时间：2026-07-28 13:29 CST | ARK Cruise Bot*
