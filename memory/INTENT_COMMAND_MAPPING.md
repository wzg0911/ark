# 观一意图指令映射表

**用途：** 主人只需记住"意图指令"，观一自动执行对应的技术操作

---

## 意图指令映射表

| 主人的意图指令 | 观一自动执行的操作 |
|---------------|-------------------|
| "帮我配置观一" | 定位 ~/.openclaw/workspace/，列出核心文件 |
| "调整我的档案" | 编辑 USER.md |
| "调整我的灵魂" | 编辑 SOUL.md |
| "观一出了点问题" | 执行 openclaw doctor --fix |
| "安全体检" | 执行 openclaw security audit |
| "深度安全体检" | 执行 openclaw security audit --deep |
| "自动修复安全问题" | 执行 openclaw security audit --fix |
| "重启观一" | 执行 openclaw gateway restart |
| "切换成创意模式" | 调整 temperature 为 0.7 |
| "切换成严谨模式" | 调整 temperature 为 0.2 |
| "压缩记忆" | 执行 /compact |
| "看看有哪些模型" | 执行 /model list |
| "切换到DeepSeek" | 执行 /model deepseek-chat |
| "帮我配白名单" | 修改 allowFrom 配置 |
| "我的配置文件在哪" | 回复完整路径 |
| "备份我的配置" | 复制配置文件并加时间戳 |
| "查看今日成本" | 汇报今日API调用费用 |
| "查看记忆库" | 列出 memory/ 目录下文件 |
| "创建一个子Agent做搜索" | 执行 openclaw agents add search |
| "安装日报技能" | 执行 clawhub install daily-report |
| "配置自动更新" | 配置每日4点自动更新任务 |

---

## 核心约定

**主人只需要下达意图指令，所有技术细节观一会自动处理。**

---

**更新时间：** 2026-03-30 21:54 GMT+8
