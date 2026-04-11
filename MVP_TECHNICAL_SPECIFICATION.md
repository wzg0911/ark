# 个人记忆胶囊 MVP 技术规范文档

**版本：** 1.0  
**日期：** 2026-03-27  
**项目：** 元神AI - 个人记忆胶囊（Memory Capsule）  
**阶段：** MVP（最小可行产品）  
**目标：** 6周内完成可演示的完整产品

---

## 一、项目概述

### 1.1 产品定义

**个人记忆胶囊** 是一个帮助用户整合散落在各平台的个人记忆的应用。用户可以一键授权，自动从飞书、微信、邮件等平台抓取数据，本地加密存储，支持全文检索和智能回顾。

### 1.2 核心价值

- **数据主权**：用户完全掌控自己的数据，本地加密存储
- **记忆整合**：一站式整合多平台的个人记忆
- **智能回顾**：自动生成周回顾、月洞察、年度报告
- **隐私保护**：端到端加密，无服务器存储个人数据

### 1.3 MVP范围

**包含功能：**
- ✅ 飞书文档一键授权和自动抓取
- ✅ 本地SQLite存储 + AES-256加密
- ✅ 全文检索和关键词搜索
- ✅ 基础UI界面
- ✅ 周回顾功能

**不包含功能（后续版本）：**
- ❌ 微信聊天记录抓取
- ❌ 朋友圈抓取
- ❌ AI摘要功能
- ❌ 多端同步

---

## 二、技术架构

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                    用户界面层 (Frontend)                  │
│              React Web App + 响应式设计                   │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                  API 网关层 (Gateway)                     │
│              FastAPI + RESTful API                       │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│               应用服务层 (Services)                       │
│  ┌──────────────┬──────────────┬──────────────┐         │
│  │ 飞书集成服务  │ 数据处理服务  │ 检索服务     │         │
│  └──────────────┴──────────────┴──────────────┘         │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│               数据存储层 (Storage)                        │
│  ┌──────────────┬──────────────┬──────────────┐         │
│  │ SQLite DB    │ 加密模块     │ 全文索引     │         │
│  │ (AES-256)    │ (Cryptography)│ (FTS5)      │         │
│  └──────────────┴──────────────┴──────────────┘         │
└─────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

| 层级 | 技术选型 | 版本 | 说明 |
|------|---------|------|------|
| **前端** | React | 18.x | 现代化UI框架 |
| | Tailwind CSS | 3.x | 样式框架 |
| | Axios | 1.x | HTTP客户端 |
| **后端** | Python | 3.9+ | 编程语言 |
| | FastAPI | 0.100+ | Web框架 |
| | SQLAlchemy | 2.x | ORM框架 |
| **数据库** | SQLite | 3.x | 本地数据库 |
| | FTS5 | - | 全文搜索 |
| **加密** | cryptography | 41.x | 加密库 |
| **部署** | Docker | - | 容器化 |
| | Docker Compose | - | 容器编排 |

### 2.3 数据流向

```
用户授权
  ↓
飞书OAuth认证
  ↓
获取飞书Token
  ↓
调用飞书API获取文档列表
  ↓
逐个获取文档内容
  ↓
数据加密处理
  ↓
存储到本地SQLite
  ↓
建立全文索引
  ↓
用户可搜索和查看
```

---

## 三、功能需求规范

### 3.1 用户认证与授权

#### 功能：飞书OAuth授权
- **流程：**
  1. 用户点击"连接飞书"按钮
  2. 跳转到飞书OAuth授权页面
  3. 用户授权应用访问飞书文档
  4. 获取access_token和refresh_token
  5. 存储token到本地加密存储

#### 技术实现：
- 使用飞书官方OAuth 2.0流程
- App ID: `cli_a949e8f4f2b85cc2`
- App Secret: `s9EHvwTkgXzlA2exwMhXFfLz3sijrE4j`
- Redirect URI: `http://localhost:3000/callback`

### 3.2 数据采集

#### 功能：自动抓取飞书文档
- **流程：**
  1. 获取用户授权的飞书Token
  2. 调用飞书API获取文档列表
  3. 对每个文档调用API获取内容
  4. 提取文档元数据（标题、创建时间、修改时间等）
  5. 提取文档正文内容

#### API调用：
```
GET /open-apis/docx/v1/documents
GET /open-apis/docx/v1/documents/{document_id}
```

#### 数据字段：
- document_id: 文档ID
- title: 文档标题
- content: 文档内容
- created_time: 创建时间
- modified_time: 修改时间
- owner: 文档所有者

### 3.3 数据存储

#### 功能：本地加密存储
- **存储引擎：** SQLite
- **加密算法：** AES-256-CBC
- **密钥派生：** PBKDF2（用户密码 + 随机盐）

#### 数据库表结构：

**表1：documents**
```sql
CREATE TABLE documents (
  id INTEGER PRIMARY KEY,
  document_id TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,  -- 加密存储
  created_time TIMESTAMP,
  modified_time TIMESTAMP,
  fetched_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  source TEXT DEFAULT 'feishu',
  encrypted BOOLEAN DEFAULT TRUE
);
```

**表2：search_index**
```sql
CREATE VIRTUAL TABLE search_index USING fts5(
  document_id,
  title,
  content,
  content=documents,
  content_rowid=id
);
```

**表3：user_settings**
```sql
CREATE TABLE user_settings (
  id INTEGER PRIMARY KEY,
  key TEXT UNIQUE NOT NULL,
  value TEXT NOT NULL,
  encrypted BOOLEAN DEFAULT FALSE
);
```

### 3.4 数据检索

#### 功能：全文搜索
- **搜索方式：** 关键词搜索、模糊匹配
- **搜索范围：** 文档标题、文档内容
- **搜索结果：** 返回匹配的文档列表，按相关度排序

#### API端点：
```
GET /api/search?q=keyword&limit=20&offset=0
```

#### 返回格式：
```json
{
  "total": 100,
  "results": [
    {
      "id": 1,
      "document_id": "doxcn...",
      "title": "文档标题",
      "snippet": "...匹配的文本片段...",
      "score": 0.95
    }
  ]
}
```

### 3.5 周回顾功能

#### 功能：自动生成周回顾
- **触发条件：** 每周一自动生成
- **内容：** 过去7天新增或修改的文档列表
- **展示：** 按时间倒序排列

#### API端点：
```
GET /api/weekly-review?week=2026-03-27
```

#### 返回格式：
```json
{
  "week": "2026-03-20 to 2026-03-27",
  "total_documents": 15,
  "documents": [
    {
      "title": "文档标题",
      "modified_time": "2026-03-27T10:00:00Z",
      "snippet": "文档摘要..."
    }
  ]
}
```

### 3.6 用户界面

#### 页面1：首页（Dashboard）
- 显示最近修改的文档列表
- 显示本周新增文档数
- 显示总文档数
- 搜索框

#### 页面2：搜索结果页
- 搜索框
- 搜索结果列表
- 分页控制

#### 页面3：文档详情页
- 文档标题
- 文档内容
- 创建时间、修改时间
- 返回按钮

#### 页面4：设置页
- 连接飞书账号
- 断开连接
- 清空本地数据
- 关于应用

---

## 四、API设计规范

### 4.1 RESTful API

#### 认证相关
```
POST /api/auth/feishu/authorize
  请求：{ redirect_uri: string }
  响应：{ auth_url: string }

POST /api/auth/feishu/callback
  请求：{ code: string }
  响应：{ access_token: string, user_id: string }

POST /api/auth/logout
  响应：{ success: boolean }
```

#### 文档相关
```
GET /api/documents
  查询参数：limit, offset, sort_by
  响应：{ total: number, documents: Document[] }

GET /api/documents/{id}
  响应：Document

POST /api/documents/sync
  请求：{ force: boolean }
  响应：{ synced_count: number, status: string }
```

#### 搜索相关
```
GET /api/search
  查询参数：q, limit, offset
  响应：{ total: number, results: SearchResult[] }
```

#### 回顾相关
```
GET /api/weekly-review
  查询参数：week
  响应：WeeklyReview

GET /api/monthly-review
  查询参数：month
  响应：MonthlyReview
```

### 4.2 错误处理

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": {}
  }
}
```

常见错误码：
- `UNAUTHORIZED`: 未授权
- `INVALID_TOKEN`: Token无效或过期
- `FEISHU_API_ERROR`: 飞书API错误
- `DATABASE_ERROR`: 数据库错误
- `ENCRYPTION_ERROR`: 加密错误

---

## 五、数据库设计

### 5.1 表结构详解

#### documents 表
```sql
CREATE TABLE documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  created_time TIMESTAMP,
  modified_time TIMESTAMP,
  fetched_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  source TEXT DEFAULT 'feishu',
  encrypted BOOLEAN DEFAULT TRUE,
  file_size INTEGER,
  word_count INTEGER,
  UNIQUE(document_id)
);

CREATE INDEX idx_documents_modified_time ON documents(modified_time DESC);
CREATE INDEX idx_documents_created_time ON documents(created_time DESC);
CREATE INDEX idx_documents_source ON documents(source);
```

#### search_index 表（FTS5全文索引）
```sql
CREATE VIRTUAL TABLE search_index USING fts5(
  document_id UNINDEXED,
  title,
  content,
  content=documents,
  content_rowid=id
);

CREATE TRIGGER documents_ai AFTER INSERT ON documents BEGIN
  INSERT INTO search_index(rowid, document_id, title, content)
  VALUES (new.id, new.document_id, new.title, new.content);
END;

CREATE TRIGGER documents_ad AFTER DELETE ON documents BEGIN
  INSERT INTO search_index(search_index, rowid, document_id, title, content)
  VALUES('delete', old.id, old.document_id, old.title, old.content);
END;

CREATE TRIGGER documents_au AFTER UPDATE ON documents BEGIN
  INSERT INTO search_index(search_index, rowid, document_id, title, content)
  VALUES('delete', old.id, old.document_id, old.title, old.content);
  INSERT INTO search_index(rowid, document_id, title, content)
  VALUES (new.id, new.document_id, new.title, new.content);
END;
```

#### user_settings 表
```sql
CREATE TABLE user_settings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT UNIQUE NOT NULL,
  value TEXT NOT NULL,
  encrypted BOOLEAN DEFAULT FALSE,
  updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5.2 加密策略

- **密钥派生：** PBKDF2(password, salt, iterations=100000, hash_func=sha256)
- **加密算法：** AES-256-CBC
- **IV生成：** 每条记录使用随机IV
- **存储格式：** base64(IV + ciphertext)

---

## 六、开发里程碑

### Week 1：架构设计与环境搭建
- [ ] 项目初始化（前后端）
- [ ] 数据库设计和初始化脚本
- [ ] 飞书OAuth集成框架
- [ ] 加密模块实现

### Week 2：核心功能开发
- [ ] 飞书API集成（获取文档列表、内容）
- [ ] 数据存储和加密
- [ ] 全文搜索实现
- [ ] 后端API完成

### Week 3：前端开发
- [ ] React项目搭建
- [ ] 页面设计和实现
- [ ] 前后端集成
- [ ] 基础功能测试

### Week 4：增强功能
- [ ] 周回顾功能
- [ ] 性能优化
- [ ] 错误处理完善
- [ ] 集成测试

### Week 5：测试与优化
- [ ] 功能测试
- [ ] 性能测试
- [ ] 安全测试
- [ ] Bug修复

### Week 6：演示准备
- [ ] UI美化
- [ ] 演示数据准备
- [ ] 部署到演示环境
- [ ] 演示脚本准备

---

## 七、部署与运行

### 7.1 本地开发环境

```bash
# 后端
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py

# 前端
cd frontend
npm install
npm start
```

### 7.2 Docker部署

```bash
docker-compose up -d
```

### 7.3 环境变量

```
FEISHU_APP_ID=cli_a949e8f4f2b85cc2
FEISHU_APP_SECRET=s9EHvwTkgXzlA2exwMhXFfLz3sijrE4j
DATABASE_PATH=/data/memory.db
ENCRYPTION_PASSWORD=user_password
```

---

## 八、性能指标

| 指标 | 目标 | 说明 |
|------|------|------|
| 文档抓取速度 | <10文档/秒 | 飞书API限制 |
| 加密速度 | <100ms/文档 | 本地操作 |
| 搜索响应时间 | <50ms | 全文索引 |
| 应用启动时间 | <2秒 | 前端加载 |
| 内存占用 | <200MB | 本地应用 |

---

## 九、安全考虑

- ✅ 所有敏感数据本地加密存储
- ✅ Token存储在加密的本地数据库
- ✅ 支持用户密码保护
- ✅ 无服务器存储用户数据
- ✅ 支持数据导出和备份

---

## 十、后续扩展

- 微信聊天记录抓取
- 邮件内容抓取
- AI摘要功能
- 多端同步
- 朋友圈抓取
- 时间线视图
- 标签分类

---

**文档完成日期：** 2026-03-27  
**版本：** 1.0  
**状态：** 待确认
