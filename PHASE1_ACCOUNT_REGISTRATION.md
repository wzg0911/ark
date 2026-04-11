# Phase 1：AI平台账号注册计划

**目标：** 注册所有必需的AI平台账号，获取API密钥

**时间：** 2026-03-27 13:33 GMT+8

---

## 需要注册的平台

### 1. Claude Code（代码生成）
- **URL：** https://claude.ai
- **需求：** 注册Claude Pro账号
- **成本：** $20/月
- **用途：** 生成完整的前后端代码

### 2. HeyGen（视频生成）
- **URL：** https://www.heygen.com
- **需求：** 注册账号，获取API密钥
- **成本：** $50/月（或按次计费）
- **用途：** 生成AI虚拟主播演示视频

### 3. 阿里云TTS（配音）
- **URL：** https://www.aliyun.com
- **需求：** 注册账号，开通语音合成服务
- **成本：** $10/月（或按次计费）
- **用途：** 生成高质量配音

### 4. 剪映（视频编辑）
- **URL：** https://www.capcut.com
- **需求：** 注册账号
- **成本：** 免费 + 高级功能$5-20/月
- **用途：** 视频编辑、字幕、特效

### 5. 即梦（国内视频生成）
- **URL：** https://jimeng.jianying.com
- **需求：** 注册账号
- **成本：** 免费额度 + 付费
- **用途：** 国内视频生成备选方案

---

## 账号注册步骤

### Step 1：Claude Code
1. 访问 https://claude.ai
2. 使用邮箱注册账号
3. 升级到Claude Pro（$20/月）
4. 获取API密钥

### Step 2：HeyGen
1. 访问 https://www.heygen.com
2. 注册账号
3. 进入Dashboard
4. 获取API密钥
5. 选择虚拟主播模板

### Step 3：阿里云TTS
1. 访问 https://www.aliyun.com
2. 注册账号
3. 进入控制台
4. 开通语音合成服务
5. 获取AccessKey和AccessSecret

### Step 4：剪映
1. 访问 https://www.capcut.com
2. 注册账号
3. 下载客户端或使用网页版

### Step 5：即梦
1. 访问 https://jimeng.jianying.com
2. 注册账号
3. 查看免费额度

---

## 账号信息存储

所有账号信息将存储在：
`/Users/w/.openclaw/workspace/.env.accounts`

格式：
```
CLAUDE_API_KEY=xxx
HEYGEN_API_KEY=xxx
ALIYUN_ACCESS_KEY=xxx
ALIYUN_ACCESS_SECRET=xxx
JIEMENG_API_KEY=xxx
```

---

**状态：** 待执行
**预计完成时间：** 2小时
