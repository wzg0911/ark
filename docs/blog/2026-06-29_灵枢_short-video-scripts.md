# 灵枢 R3 — 短视频脚本系列

> 产出日期：2026-06-29  
> 格式：抖音 / TikTok / YouTube Shorts（9:16 竖屏）  
> 目标受众：AI Agent 开发者、后端工程师、SaaS 创业者

---

## 📹 视频1：《你的Agent扣了用户几次款？》

| 时长 | 镜头 | 时间 | 画面 | 字幕 | 音效 |
|------|------|------|------|------|------|
| 15s | 9:16 | 0-3s | 纯黑背景，白色文字居中淡入 | "你的AI Agent刚刚..." | 心跳声，渐强 |
| | | 2-3s | 一闪而过：红色"$49.99" | — | 收银机"叮" |
| | | 3-5s | 三张Stripe风格扣款记录快速闪过，每张带红色"DUPLICATE"印章 | 无字幕 | 每一次闪过配"咔嚓"快门声 |
| | | | 第一张：`ch_3Nx... $49.99 — Duplicate` | | |
| | | | 第二张：`ch_3Ny... $49.99 — Duplicate` | | |
| | | | 第三张：`ch_3Nz... $49.99 — Duplicate` | | |
| | | 5-6s | 黑屏过渡 | — | 静默0.5s |
| | | 6-8s | 终端界面出现，逐字键入 | "每次重复扣款，都是信任的流失。" | 机械键盘敲击声 |
| | | 8-11s | 终端中打出 `pip install ark-trust`，回车后显示绿色 `✓ Successfully installed` | 同上 | Enter键清脆一声，随后"叮"成功音 |
| | | 11-13s | 三段Python代码逐行浮现： | "3行代码。" | 每行出现配轻敲击 |
| | | | `from ark import TrustLayer` | | |
| | | | `tl = TrustLayer()` | | |
| | | | `result = tl.safe_call(payment, idempotency_key=order_id)` | | |
| | | 13-15s | 代码消失，居中大字 + GitHub 链接 | "永不重复。" | 重低音Boom + 结束音 |
| | | | `github.com/wzg0911/ark` | | |

**拍摄建议：**
- 0-3s用手机黑屏反光拍摄，营造紧张悬念
- Stripe截图用真实Dashboard截图打码处理，增强真实感
- 终端动画用 [termynal.js](https://termynal.github.io/termynal.js/) 或 Keynote 打字机效果
- 3行代码部分用代码高亮截图，Sublime Text / VS Code 暗色主题

---

## 📹 视频2：《8847个Bug的共同原因》

| 时长 | 镜头 | 时间 | 画面 | 字幕 | 音效 |
|------|------|------|------|------|------|
| 20s | 9:16 | 0-1s | 深蓝渐变背景，React Logo 淡入 | — | 低音嗡鸣 |
| | | 1-3s | React Logo 下方数字从0快速滚动到 `3,247` | "3,247 open error issues" | 数字滚动声（老虎机风格） |
| | | 3-4s | React淡出，Next.js Logo淡入 | — | 过渡滑音 |
| | | 4-6s | Next.js下方数字滚动到 `2,891` | "2,891 open error issues" | 数字滚动声 |
| | | 6-7s | Next.js淡出，Node.js Logo淡入 | — | 过渡滑音 |
| | | 7-9s | Node.js下方数字滚动到 `2,709` | "2,709 open error issues" | 数字滚动声 |
| | | 9-10s | 三Logo并排缩小到屏幕上方1/3 | 总计：8,847个Bug | "Boom"一声汇总 |
| | | 10-15s | 屏幕中下部：标签云爆发式飞出，词条快速闪过： | — | 快速打字/闪现音效 |
| | | | `retry` `timeout` `duplicate` `crash` | | |
| | | | `race-condition` `dead-letter` `null-pointer` | | |
| | | | `connection-reset` `idempotency` `circuit-breaker` | | |
| | | | `rate-limit` `retry-storm` `poison-pill` | | |
| | | 15-17s | 所有标签收缩、聚拢，汇聚成一个词 | — | 收缩音效（倒放爆炸） |
| | | 17-18s | 居中大字，黑底白字 | "No Reliability Layer" | 重低音 |
| | | 18-20s | 黑屏上ARK Logo亮起 | "The missing piece." | 品牌Jingle / 清脆"叮" |

**拍摄建议：**
- 数字滚动用 CSS counter 动画或 After Effects Number effect
- 标签云用 [WordCloud](https://github.com/jasondavies/d3-cloud) 或 AE Particular
- 标签汇聚那段是核心视觉冲击：70+标签分散→汇聚成一个词，用AE粒子效果
- 三框架Logo用官方SVG，保持清晰
- 数据来源可标注小字：GitHub Issues (filter: bug + error, as of 2026 Q2)

---

## 📹 视频3：《熔断器救了500个Agent》

| 时长 | 镜头 | 时间 | 画面 | 字幕 | 音效 |
|------|------|------|------|------|------|
| 20s | 9:16 | 0-1s | 监控Dashboard界面（Grafana风格），顶部标题 "Agent Fleet — 500 Active" | — | 服务器嗡嗡声 |
| | | 1-2s | 第一个节点变红 ❌，Agent计数 500→499 | — | 警报"哔" |
| | | 2-3s | 第2、3个节点接连变红 | — | 连续警报声 |
| | | 3-5s | 像多米诺骨牌：红色节点指数级扩散，Agent计数快速跌至0 | — | 警报声越来越密集，最后长鸣 |
| | | 5-5.5s | 全红Dashboard停留0.5秒，Agent计数=0 | — | 静默 |
| | | 5.5-6s | 屏幕中央出现一行代码：`cb = CircuitBreaker()` | "但有一条线..." | 打字声 |
| | | 6-8s | 代码淡出，ARK CircuitBreaker 图标（断路器开关）出现 | — | 开关闭合"咔哒" |
| | | 8-9s | 第一个红灯变回绿灯 🟢 | — | "叮" |
| | | 9-12s | 像多米诺反转：全部节点从红变绿，500个Agent全部恢复 | — | 连续"叮"声，越来越密集 |
| | | 12-13s | Dashboard回到绿色，Agent计数=500 | — | 胜利和弦 |
| | | 13-15s | 大字居中显示： | "99.7% Uptime" | 数据滚动音 |
| | | 15-16s | 切换： | "0 Cascading Failures" | 同上 |
| | | 16-17s | 切换： | "3 Lines of Code" | 同上 |
| | | 17-18s | 三行数据缩小到上方 | — | 过渡 |
| | | 18-20s | ARK Logo + GitHub 链接 | "github.com/wzg0911/ark" | 品牌Jingle |

**拍摄建议：**
- Dashboard用Grafana截图/录屏（或Figma模拟），绿色圆点=健康节点，红色=故障
- 多米诺效果是关键：节点按网络拓扑顺序逐个变红/变绿，用AE cascade动画
- 断路器图标用ARK Logo的电闸/保险丝元素特写
- 数据部分用大号粗体数字，带滚动进入动画
- BGM建议：前半段紧张弦乐→断路器出现后切换为希望感电子乐

---

## 🎬 系列统一风格指南

| 元素 | 规范 |
|------|------|
| 画幅 | 9:16 竖屏（1080×1920） |
| 字体 | 黑体/Inter Bold（标题），DIN/Menlo（代码） |
| 品牌色 | ARK 蓝 `#2563EB`，白 `#FFFFFF`，黑 `#0A0A0A` |
| CTA | 所有视频末尾统一：ARK Logo + `github.com/wzg0911/ark` |
| 长度 | 15-20秒，节奏紧，无废话 |
| BGM | 电子/科技感，无人声干扰，结尾留品牌Jingle空间 |

---

## 🏷️ 标题库（抖音/TikTok风格 — 新增）

| # | 标题 | 适用视频 | 策略 |
|---|------|----------|------|
| 1 | 《你的Agent刚刚替你花了冤枉钱》 | 视频1 | 悬念+痛点，触发焦虑 |
| 2 | 《3行代码，省下50万退款纠纷》 | 视频1 | 数字对比，制造反差 |
| 3 | 《我统计了8847个Bug，全是同一个问题》 | 视频2 | 数据震撼+结论反直觉 |
| 4 | 《为什么你的Agent总是炸？答案在这里》 | 视频2 | 痛点直击+钩子 |
| 5 | 《500个Agent同时崩了，我按下了一个按钮》 | 视频3 | 叙事悬念+反转期待 |
| 6 | 《熔断器：AI Agent的隐形守护者》 | 视频3 | 拟人化+价值锚定 |
| 7 | `别再让你的Agent裸奔了` | 通用 | 口语化警告，唤起不安 |
| 8 | `Agent可靠性只需3行代码` | 通用 | 极简承诺，降低心理门槛 |
| 9 | `我开源了一个Agent安全层` | 通用 | 开发者真诚分享风格 |

---

## 📊 灵枢 R1-R3 产出总览

| 轮次 | 产出 | 文件 |
|------|------|------|
| R1 | 3分钟分镜脚本（技术叙事型） | `2026-06-29_灵枢_storyboard.md` |
| R2 | 5条Twitter推文 + 3条沸点 | `2026-06-29_灵枢_tweet-thread.md` |
| **R3** | **3个短视频脚本 + 标题库** | **`2026-06-29_灵枢_short-video-scripts.md`** |

---

*灵枢 R3 完成。视觉内容三轮全部交付。*
