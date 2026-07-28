# ARK 复利飞轮每日巡航报告 — 2026-07-21

> 巡航时间：2026-07-21 16:13 (Asia/Shanghai) | 执行：ARK 自动巡航

## 一、核心指标总览

| 指标 | wzg0911/ark | wzg0911/ark-ts | 状态 |
|------|------------:|---------------:|------|
| GitHub Stars | 0 | 0 | 🔴 停滞 |
| Forks | 0 | 0 | — |
| Watchers | 0 | 0 | — |
| Open Issues | 1（垃圾/钓鱼） | 0 | 🟡 需处理 |
| PyPI `ark-trust` 月下载 | 211（周 2 / 日 0） | — | ✅ 达标但衰减 |
| npm `@feilunxitong/arkit` 月下载 | — | 269（周 17） | ✅ 达标但衰减 |
| Badge Service 健康 | — | `ark-badge-service.vercel.app/api/health` | 🔴 宕机 |

## 二、增长目标进展

- **Week 1 — Star > 10：** 🔴 当前 0。严重停滞，从未做过公开发布。本次巡航已补齐发布（见第四节），需配合推广。
- **Week 2 — PyPI 下载 > 100：** ✅ 月下载 211（达标）。但近一周仅 2、当日 0，增长来自 6 月早期脉冲，目前衰减明显。
- **Week 4 — npm 下载 > 100：** ✅ 月下载 269（达标，若按周口径则 17 未达标）。近一周 17，动量同样偏低。

> 结论：下载量靠早期脉冲冲过 100，但**自然增长已熄火**；Stars 从未启动。当前首要矛盾是「零公开曝光 → 零 Star」。

## 三、异常与处理

### 🔴 异常 1：Badge Service 宕机
- 现象：`curl https://ark-badge-service.vercel.app/api/health` 返回 `HTTP 000 / Connection reset by peer`（DNS 可解析，TLS 被对端重置）。
- 判定：服务不可用（疑似 Vercel 项目被暂停/删除或路由失效）。经排查 README 未引用该地址（主文档走 shields.io），故**不影响用户可见文档**，但作为受监控状态服务已离线。
- 修复尝试：本机未配置 Vercel 凭证（`vercel whoami` → No credentials），**无法直接重新部署**。已记录，需主人在 Vercel Dashboard 检查 `ark-badge-service` 项目并重新部署。

### 🟡 异常 2：Issue #1 为垃圾/钓鱼
- 现象：标题伪装成 CrewAI 崩溃问题，正文是外部产品 **TrustLoop**（soji@trustloop.live）的销售私信，属竞品推广/钓鱼。
- 修复尝试：当前 fine-grained Token 无 `issues:write` 权限，无法关闭。需主人手动关闭（或提升 Token 权限后由巡航自动清理）。

## 四、本次已执行的动作（自动）

1. ✅ **发布 GitHub Release v0.7.0**（此前 v0.4.1~v0.7.0 仅有 tag 无 Release）：
   https://github.com/wzg0911/ark/releases/tag/v0.7.0 — 含完整价值主张、四支柱、3 行接入、在线诊断链接，作为可分享的发布资产。
2. ✅ **写入推广工具包** `PROMOTION/launch-kit.md`（已推送到 main）：含 Show HN、r/LocalLLaMA、r/Python、V2EX、X 等平台的**可直接复制粘贴**文案，供主人一键发布。

## 五、需要主人处理（人工动作）

1. ** redeploy Badge Service**：登录 Vercel，检查 `ark-badge-service` 项目状态并重新部署；确认 `/api/health` 恢复 200。
2. **关闭垃圾 Issue #1**：https://github.com/wzg0911/ark/issues/1 （建议顺手举报为 spam）。
3. **执行推广**：按 `PROMOTION/launch-kit.md` 发布 Show HN + Reddit + V2EX，这是把 Star 从 0 推过 10 的最快路径（建议周二~周四 美西 9–11 点发 Show HN）。
4. （可选）为 `wzg0911/ark` 开启 GitHub Discussions，承接问答、转化 Star。

## 六、下一步

- 持续监控 Star 是否随发布+推广抬升；若 48h 内仍 0，下个巡航将追加内容矩阵（技术长文 / demo 视频 / 开发者社区问答）。
- 下载量衰减已标记，推广包同步覆盖 PyPI/npm 回流。
- Badge Service 恢复后巡航将自动校验并解除告警。
