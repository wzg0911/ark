# 观一配置参数说明

## 核心配置文件位置
`~/.openclaw/openclaw.json`

---

## 核心参数

| 参数 | 作用 | 推荐值 | 说明 |
|------|------|--------|------|
| temperature | 控制创造力/严谨度 | 0.2（逻辑）→ 0.7（创意） | 日常用0.2，更"听话" |
| contextPruning | 自动裁剪旧对话省Token | true，TTL设5分钟 | 避免上下文无限膨胀 |
| compaction.mode | 防记忆丢失 | safeguard | 关键信息不丢失 |
| session.reset.mode | 会话重置策略 | daily | 每天凌晨4点重置 |
| session.reset.atHour | 重置时间 | 4 | 凌晨4点 |
| sandbox.mode | 安全隔离 | non-main | 非核心任务在隔离沙箱运行 |
| dmPolicy | 新用户私聊策略 | pairing | 需配对码确认，防骚扰 |
| groups.*.requireMention | 群聊响应规则 | true | 必须@才回复 |

---

## 配置示例

```json
{
  "agents": {
    "defaults": {
      "workspace": "~/.openclaw/workspace",
      "temperature": 0.2,
      "sandbox": {
        "mode": "non-main"
      }
    }
  },
  "session": {
    "dmScope": "per-channel-peer",
    "reset": {
      "mode": "daily",
      "atHour": 4
    }
  },
  "channels": {
    "whatsapp": {
      "allowFrom": ["+86你的手机号"],
      "groups": {
        "*": {
          "requireMention": true
        }
      },
      "dmPolicy": "pairing"
    }
  },
  "memory": {
    "backend": "qmd",
    "qmd": {
      "command": "qmd",
      "scope": {
        "default": "allow"
      },
      "limits": {
        "maxResults": 6,
        "timeoutMs": 8000
      }
    }
  }
}
```

---

## 安全配置

### 安全核心原则
**永远不要用 root 用户运行观一！**

观一能控制浏览器、执行shell命令、读写文件，用root等于把整个服务器交给AI。必须创建专用用户运行。

### 专用用户创建（Linux/云服务器）
```bash
# 创建专用用户
sudo useradd -m -s /bin/bash openclaw

# 切换到专用用户
su - openclaw

# 在该用户下安装和运行观一
```

### 白名单配置（防止陌生人消耗API）
```json
"channels": {
  "whatsapp": {
    "allowFrom": ["+86你的手机号"],
    "dmPolicy": "pairing"
  }
}
```

### 工具权限隔离（禁止高危操作）
```json
{
  "tools": {
    "deny": ["exec", "write", "edit", "apply_patch", "delete"]
  }
}
```

或更精细地：
```json
"gateway": {
  "nodes": {
    "denyCommands": ["camera.snap", "screen.record", "shell.exec", "fs.delete"]
  }
}
```

---

## QMD记忆系统

### 为什么需要QMD？
- **智能上下文管理：** 只加载相关记忆，而非全量历史
- **响应速度飞跃：** 检索时间恒定（约100ms）
- **成本断崖式下降：** Token消耗减少60-97%

### QMD安装
```bash
# 安装QMD CLI（全平台）
npm install -g github:tobi/qmd

# 验证安装
qmd --version
```

### 配置QMD集成
```json
"memory": {
  "backend": "qmd",
  "qmd": {
    "command": "qmd",
    "scope": {
      "default": "allow"
    },
    "limits": {
      "maxResults": 6,
      "timeoutMs": 8000
    }
  }
}
```

### 初始化记忆库
```bash
# 进入工作区
cd ~/.openclaw/workspace

# 创建集合
qmd collection add . --name workspace

# 更新索引
qmd update --dir ~/.openclaw/workspace
```

---

## 多Agent协作配置（进阶）

### 创建子Agent
```bash
# 创建搜索Agent
openclaw agents add search --workspace ~/.openclaw/workspace-search

# 创建写作Agent
openclaw agents add write --workspace ~/.openclaw/workspace-write

# 创建代码Agent
openclaw agents add code --workspace ~/.openclaw/workspace-code
```

### 配置路由规则（Bindings）
```json
"bindings": [
  {
    "agentId": "search",
    "match": {
      "channel": "discord",
      "peer": {
        "kind": "channel",
        "id": "频道ID1"
      }
    }
  },
  {
    "agentId": "write",
    "match": {
      "channel": "discord",
      "peer": {
        "kind": "channel",
        "id": "频道ID2"
      }
    }
  }
]
```

### 验证Agent状态
```bash
openclaw agents list --bindings
```

---

## 救急命令集（万能钥匙）

| 问题场景 | 命令 | 说明 |
|---------|------|------|
| 配置错误、启动失败 | `openclaw doctor --fix` | 万能救急，自动检测并修复 |
| 配置文件损坏 | `cp openclaw.json openclaw.json.bak` | 先备份再修改 |
| 网关卡死 | `openclaw gateway restart` | 重启网关 |
| 模型切换 | `openclaw models set <模型名>` | 临时换脑子 |
| 查看已装技能 | `clawhub list` | 技能管理 |
| 压缩对话上下文 | `/compact` | 长对话后执行，省Token |
| 查看可用模型 | `/model list` | 查看可切换的模型 |
| 临时切换模型 | `/model <模型名>` | 不影响全局配置 |

---

---

## 安全配置（P0）

### 安全审计命令

| 命令 | 用途 |
|------|------|
| `openclaw security audit` | 常规安全检查 |
| `openclaw security audit --deep` | 深度探测（模拟攻击者视角） |
| `openclaw security audit --fix` | 自动修复常见安全问题 |

**审计检查核心内容：**

| 检查项 | 问题 | 风险 |
|-------|------|------|
| 入站访问 | 陌生人能否触发机器人？ | 陌生人消耗API、恶意诱导 |
| 工具影响范围 | 提示词注入能否转化为shell/文件操作？ | AI被操纵执行危险命令 |
| 网络暴露 | Gateway网关认证是否暴露？ | 外部攻击 |
| 浏览器控制暴露 | 远程CDP端点是否暴露？ | 远程控制风险 |
| 本地权限 | 配置文件权限是否过宽？ | 信息泄露 |
| 插件/扩展 | 是否存在未白名单的插件？ | 恶意代码执行 |

### 核心安全原则

**最重要的原则：不要用root用户运行！**

**必须创建专用用户运行：**
```bash
sudo useradd -m -s /bin/bash openclaw
su - openclaw
```

### 白名单配置（防陌生人消耗API）

```json
"channels": {
  "whatsapp": {
    "allowFrom": ["+86你的手机号"],
    "dmPolicy": "pairing"
  }
}
```

**dmPolicy说明：**
- `pairing`（默认）：未知发送者会收到配对码，需你批准后才能对话
- `allowlist`：未知发送者被直接阻止
- `open`：允许任何人发私信（危险！）
- `disabled`：完全忽略入站私信

### 群聊响应规则（防吵死）

```json
"channels": {
  "groups": {
    "*": { "requireMention": true }
  }
}
```

### 恶意Skill检测规范

安天安全报告揭示：ClawHub已出现大规模Skill投毒攻击，攻击者批量上传伪装成加密货币工具、办公助手的恶意Skills，可窃取SSH密钥、浏览器密码、加密钱包。

**安全规范：**
1. 安装任何Skill前必须用 `openclaw vet <技能名>` 审查
2. 只装带绿色"安全标"的技能
3. 避免零下载量的"三无技能"
4. 定期执行 `openclaw vet --all` 全量扫描

已将这些恶意样本统一命名为 `Trojan/OpenClaw.PolySkill`。

---

## 实用技能装配

### 自动更新技能

```bash
clawhub install auto-updater
```

配置每日自动更新：
```bash
openclaw cron add \
  --name "Daily Auto-Update" \
  --cron "0 4 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --wake now \
  --deliver \
  --message "执行每日自动更新流程"
```

### 每日日报技能

```bash
clawhub install daily-report
```

---

**更新时间：** 2026-03-30 22:03 GMT+8
