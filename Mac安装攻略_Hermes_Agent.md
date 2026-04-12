# Hermes Agent Mac安装攻略

**适用系统：** macOS 12.6.5 (Monterey)  
**架构：** x86_64 (Intel)  
**日期：** 2026-04-12  
**编写者：** 观一

---

## 一、环境检查

```bash
# 打开终端，检查以下信息
sw_vers -productVersion        # macOS版本: 12.6.5 ✅
python3 --version              # Python: 3.9.6 ✅
git --version                  # Git: 2.37.1 ✅
curl --version | head -1       # curl: 7.87.0 ✅
df -h ~ | tail -1              # 磁盘: 122Gi可用 ✅
```

**结论：基础环境具备，关键问题是网络。**

---

## 二、网络问题说明

**已知问题：**
- GitHub.com ❌ 无法直接访问（被墙）
- raw.githubusercontent.com ❌ 无法直接访问
- 国内镜像（Gitee、阿里云）✅ 可正常访问

**解决方案：** 使用GitHub镜像站下载安装脚本

---

## 三、安装方案A：一键安装（推荐）

### 步骤1：使用镜像下载安装脚本

```bash
# 方案A1：使用ghproxy镜像
curl -fsSL https://mirror.ghproxy.com/https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# 方案A2：如果A1失败，使用gh-proxy.com
curl -fsSL https://gh-proxy.com/https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

### 步骤2：等待安装完成

安装脚本会自动：
1. 安装 uv（Python包管理器）
2. 安装 Python 3.11（不覆盖系统Python）
3. 安装 Node.js v22
4. 安装 ripgrep 和 ffmpeg
5. 克隆 hermes-agent 仓库
6. 创建虚拟环境
7. 安装所有依赖
8. 创建全局 hermes 命令

**预计耗时：** 5-10分钟（取决于网络速度）

### 步骤3：重新加载Shell配置

```bash
source ~/.bashrc
# 或者如果是zsh
source ~/.zshrc
```

### 步骤4：启动Hermes

```bash
hermes
```

首次启动会提示配置LLM提供商。

---

## 四、安装方案B：手动安装（网络受限时）

如果一键安装失败，采用手动安装：

### 步骤1：配置Git镜像

```bash
# 配置GitHub镜像
git config --global url."https://mirror.ghproxy.com/https://github.com".insteadOf "https://github.com"
```

### 步骤2：手动安装前置依赖

```bash
# 安装Homebrew（如果没有）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 通过Homebrew安装依赖
brew install python@3.11 node ripgrep ffmpeg uv
```

### 步骤3：克隆仓库（使用镜像）

```bash
# 使用镜像克隆
git clone --recurse-submodules https://mirror.ghproxy.com/https://github.com/NousResearch/hermes-agent.git
cd hermes-agent
```

### 步骤4：创建虚拟环境并安装

```bash
# 创建虚拟环境
uv venv venv --python 3.11

# 安装所有依赖
export VIRTUAL_ENV="$(pwd)/venv"
uv pip install -e ".[all]"

# 创建全局命令别名
echo 'alias hermes="$(pwd)/venv/bin/hermes"' >> ~/.bashrc
source ~/.bashrc
```

---

## 五、配置LLM提供商

Hermes支持多种LLM提供商，以下是推荐方案：

### 方案1：使用DeepSeek（国内推荐）

```bash
# 设置DeepSeek API Key
export DEEPSEEK_API_KEY="your_deepseek_api_key"

# 或者在Hermes中配置
hermes model
# 选择 DeepSeek
```

### 方案2：使用阿里云灵积（DashScope）

```bash
export DASHSCOPE_API_KEY="your_dashscope_api_key"
hermes model
# 选择 Alibaba Cloud
```

### 方案3：使用OpenRouter（多模型路由）

```bash
export OPENROUTER_API_KEY="your_openrouter_api_key"
hermes model
# 选择 OpenRouter
```

### 方案4：使用本地模型（Ollama）

```bash
# 先安装Ollama
brew install ollama

# 拉取模型
ollama pull qwen2.5:14b

# 配置Hermes使用本地端点
hermes config set model.provider custom
hermes config set model.base_url http://localhost:11434/v1
```

---

## 六、验证安装

```bash
# 启动Hermes
hermes

# 看到欢迎界面后，输入测试命令
/help                    # 查看帮助
/tools                   # 查看可用工具
hermes doctor            # 诊断问题
hermes --version         # 查看版本
```

---

## 七、常见问题排查

### 问题1：uv安装失败

```bash
# 手动安装uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

### 问题2：Python 3.11下载失败

```bash
# 使用Homebrew安装
brew install python@3.11
```

### 问题3：Node.js版本不兼容

```bash
# 使用nvm管理Node版本
brew install nvm
nvm install 22
nvm use 22
```

### 问题4：ffmpeg缺失

```bash
brew install ffmpeg
```

### 问题5：网络始终无法连接

**临时方案：** 使用VPN或代理

```bash
# 配置代理（如果有）
export https_proxy=http://127.0.0.1:7890
export http_proxy=http://127.0.0.1:7890
```

---

## 八、安装后配置建议

### 1. 配置沙箱终端（推荐）

```bash
# 使用Docker隔离（更安全）
hermes config set terminal.backend docker

# 或使用SSH远程执行
hermes config set terminal.backend ssh
```

### 2. 配置消息平台

```bash
hermes gateway setup
# 按提示配置Telegram/Discord/Slack等
```

### 3. 配置语音模式（可选）

```bash
pip install "hermes-agent[voice]"
pip install faster-whisper

# 在Hermes中启用
/voice on
```

### 4. 配置定时任务

```bash
# 在对话中直接描述
"每天早上9点，汇总AI新闻发送到我的Telegram"
```

---

## 九、下一步学习

安装完成后，建议学习：

1. **CLI基础命令：** /help, /tools, /skills, /model
2. **技能系统：** hermes skills search xxx
3. **消息网关：** hermes gateway setup
4. **MCP集成：** 连接外部工具
5. **ACP编辑器集成：** VS Code / Zed 中使用

---

## 十、关键链接

- 官方文档：https://hermes-agent.nousresearch.com/docs/
- GitHub仓库：https://github.com/NousResearch/hermes-agent
- 镜像下载：https://mirror.ghproxy.com/
- Discord社区：https://discord.gg/NousResearch

---

**安装前请确保：**
1. ✅ 网络可访问GitHub（或使用镜像）
2. ✅ 磁盘空间 > 5GB
3. ✅ 不要用sudo运行安装脚本
4. ✅ 准备好LLM API Key（DeepSeek/阿里云/OpenRouter等）

---

**编写者：** 观一  
**更新时间：** 2026-04-12 14:50 GMT+8