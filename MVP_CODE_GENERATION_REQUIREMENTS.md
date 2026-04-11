# 个人记忆胶囊 MVP - 完整代码生成需求文档

**版本：** 1.0  
**日期：** 2026-03-27  
**项目：** 元神AI - 个人记忆胶囊（Memory Capsule）  
**目标：** 生成完整、可运行、生产级别的代码  
**交付物：** 完整的前后端代码包 + 部署脚本

---

## 一、项目结构

```
memory-capsule/
├── backend/
│   ├── main.py                 # FastAPI主应用
│   ├── requirements.txt         # Python依赖
│   ├── .env.example            # 环境变量示例
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py           # 配置管理
│   │   ├── database.py         # 数据库连接
│   │   ├── encryption.py       # 加密模块
│   │   ├── models.py           # 数据模型
│   │   ├── schemas.py          # Pydantic schemas
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py         # 认证路由
│   │   │   ├── documents.py    # 文档路由
│   │   │   ├── search.py       # 搜索路由
│   │   │   └── review.py       # 回顾路由
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── feishu.py       # 飞书集成
│   │   │   ├── storage.py      # 数据存储
│   │   │   └── search.py       # 搜索服务
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── logger.py       # 日志工具
│   └── tests/
│       ├── __init__.py
│       ├── test_auth.py
│       ├── test_documents.py
│       └── test_search.py
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── public/
│   │   ├── index.html
│   │   └── favicon.ico
│   ├── src/
│   │   ├── index.js
│   │   ├── App.js
│   │   ├── App.css
│   │   ├── components/
│   │   │   ├── Header.js
│   │   │   ├── Sidebar.js
│   │   │   ├── Dashboard.js
│   │   │   ├── SearchBar.js
│   │   │   ├── DocumentList.js
│   │   │   ├── DocumentDetail.js
│   │   │   ├── WeeklyReview.js
│   │   │   └── Settings.js
│   │   ├── pages/
│   │   │   ├── HomePage.js
│   │   │   ├── SearchPage.js
│   │   │   ├── DetailPage.js
│   │   │   └── SettingsPage.js
│   │   ├── services/
│   │   │   ├── api.js         # API客户端
│   │   │   └── auth.js        # 认证服务
│   │   ├── hooks/
│   │   │   ├── useAuth.js
│   │   │   ├── useDocuments.js
│   │   │   └── useSearch.js
│   │   ├── styles/
│   │   │   ├── index.css
│   │   │   ├── components.css
│   │   │   └── pages.css
│   │   └── utils/
│   │       ├── constants.js
│   │       └── helpers.js
├── docker-compose.yml
├── Dockerfile
├── .gitignore
└── README.md
```

---

## 二、后端代码生成需求

### 2.1 main.py - FastAPI主应用

**需求：**
- 创建FastAPI应用实例
- 配置CORS中间件
- 配置日志系统
- 注册所有路由
- 启动事件：初始化数据库
- 关闭事件：清理资源
- 健康检查端点

**关键代码段：**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, documents, search, review
from app.database import init_db

app = FastAPI(title="Memory Capsule API", version="1.0.0")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(review.router, prefix="/api/review", tags=["review"])

@app.on_event("startup")
async def startup():
    init_db()

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 2.2 app/config.py - 配置管理

**需求：**
- 环境变量加载
- 飞书配置
- 数据库配置
- 加密配置
- 日志配置

**关键配置：**
```python
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 飞书配置
    FEISHU_APP_ID: str = "cli_a949e8f4f2b85cc2"
    FEISHU_APP_SECRET: str = "s9EHvwTkgXzlA2exwMhXFfLz3sijrE4j"
    FEISHU_REDIRECT_URI: str = "http://localhost:3000/callback"
    
    # 数据库配置
    DATABASE_PATH: str = "./data/memory.db"
    
    # 加密配置
    ENCRYPTION_PASSWORD: str = "default_password"
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### 2.3 app/database.py - 数据库连接

**需求：**
- SQLite连接管理
- 表创建脚本
- 全文索引创建
- 触发器创建
- 连接池管理

**关键功能：**
```python
import sqlite3
from app.config import settings

def get_db():
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # 创建documents表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_time TIMESTAMP,
            modified_time TIMESTAMP,
            fetched_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source TEXT DEFAULT 'feishu',
            encrypted BOOLEAN DEFAULT TRUE
        )
    ''')
    
    # 创建全文索引
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
            document_id UNINDEXED,
            title,
            content,
            content=documents,
            content_rowid=id
        )
    ''')
    
    conn.commit()
    conn.close()
```

### 2.4 app/encryption.py - 加密模块

**需求：**
- AES-256-CBC加密
- PBKDF2密钥派生
- Base64编码/解码
- 随机IV生成

**关键功能：**
```python
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import os
import base64

class EncryptionManager:
    def __init__(self, password: str):
        self.password = password
        self.salt = b'fixed_salt_for_demo'  # 生产环境应使用随机盐
    
    def _derive_key(self) -> bytes:
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.password.encode()))
        return key
    
    def encrypt(self, plaintext: str) -> str:
        f = Fernet(self._derive_key())
        ciphertext = f.encrypt(plaintext.encode())
        return ciphertext.decode()
    
    def decrypt(self, ciphertext: str) -> str:
        f = Fernet(self._derive_key())
        plaintext = f.decrypt(ciphertext.encode())
        return plaintext.decode()
```

### 2.5 app/models.py - 数据模型

**需求：**
- SQLAlchemy ORM模型
- Document模型
- UserSettings模型
- 关系定义

**关键模型：**
```python
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True)
    document_id = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_time = Column(DateTime)
    modified_time = Column(DateTime)
    fetched_time = Column(DateTime, default=datetime.utcnow)
    source = Column(String, default="feishu")
    encrypted = Column(Boolean, default=True)

class UserSettings(Base):
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=False)
    encrypted = Column(Boolean, default=False)
```

### 2.6 app/schemas.py - Pydantic Schemas

**需求：**
- 请求/响应数据验证
- 类型提示
- 文档字符串

**关键Schemas：**
```python
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class DocumentBase(BaseModel):
    title: str
    content: str

class DocumentCreate(DocumentBase):
    document_id: str

class DocumentResponse(DocumentBase):
    id: int
    document_id: str
    created_time: Optional[datetime]
    modified_time: Optional[datetime]
    
    class Config:
        from_attributes = True

class SearchResult(BaseModel):
    id: int
    document_id: str
    title: str
    snippet: str
    score: float

class WeeklyReviewResponse(BaseModel):
    week: str
    total_documents: int
    documents: List[DocumentResponse]
```

### 2.7 app/api/auth.py - 认证路由

**需求：**
- 飞书OAuth授权URL生成
- 回调处理
- Token存储
- 登出功能

**关键端点：**
```python
from fastapi import APIRouter, HTTPException
from app.services.feishu import FeishuService

router = APIRouter()
feishu_service = FeishuService()

@router.post("/feishu/authorize")
async def authorize(redirect_uri: str):
    auth_url = feishu_service.get_auth_url(redirect_uri)
    return {"auth_url": auth_url}

@router.post("/feishu/callback")
async def callback(code: str):
    try:
        token_data = feishu_service.exchange_code_for_token(code)
        return {
            "access_token": token_data["access_token"],
            "user_id": token_data["user_id"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/logout")
async def logout():
    return {"success": True}
```

### 2.8 app/api/documents.py - 文档路由

**需求：**
- 获取文档列表
- 获取文档详情
- 同步文档
- 删除文档

**关键端点：**
```python
from fastapi import APIRouter, Query
from app.services.storage import StorageService

router = APIRouter()
storage_service = StorageService()

@router.get("/")
async def list_documents(limit: int = Query(20), offset: int = Query(0)):
    documents = storage_service.get_documents(limit, offset)
    total = storage_service.count_documents()
    return {"total": total, "documents": documents}

@router.get("/{doc_id}")
async def get_document(doc_id: int):
    document = storage_service.get_document(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@router.post("/sync")
async def sync_documents(force: bool = False):
    synced_count = storage_service.sync_from_feishu(force)
    return {"synced_count": synced_count, "status": "success"}
```

### 2.9 app/api/search.py - 搜索路由

**需求：**
- 全文搜索
- 关键词搜索
- 分页
- 排序

**关键端点：**
```python
from fastapi import APIRouter, Query
from app.services.search import SearchService

router = APIRouter()
search_service = SearchService()

@router.get("/")
async def search(
    q: str = Query(...),
    limit: int = Query(20),
    offset: int = Query(0)
):
    results = search_service.search(q, limit, offset)
    total = search_service.count_results(q)
    return {"total": total, "results": results}
```

### 2.10 app/api/review.py - 回顾路由

**需求：**
- 周回顾
- 月回顾
- 年回顾

**关键端点：**
```python
from fastapi import APIRouter, Query
from app.services.storage import StorageService
from datetime import datetime, timedelta

router = APIRouter()
storage_service = StorageService()

@router.get("/weekly")
async def weekly_review(week: str = Query(None)):
    if not week:
        week = datetime.now().strftime("%Y-%m-%d")
    
    documents = storage_service.get_weekly_documents(week)
    return {
        "week": week,
        "total_documents": len(documents),
        "documents": documents
    }

@router.get("/monthly")
async def monthly_review(month: str = Query(None)):
    if not month:
        month = datetime.now().strftime("%Y-%m")
    
    documents = storage_service.get_monthly_documents(month)
    return {
        "month": month,
        "total_documents": len(documents),
        "documents": documents
    }
```

### 2.11 app/services/feishu.py - 飞书集成

**需求：**
- OAuth认证
- 获取文档列表
- 获取文档内容
- Token刷新

**关键功能：**
```python
import requests
from app.config import settings

class FeishuService:
    BASE_URL = "https://open.feishu.cn"
    
    def get_auth_url(self, redirect_uri: str) -> str:
        return f"{self.BASE_URL}/open-apis/oauth/v3/authorize?" \
               f"client_id={settings.FEISHU_APP_ID}&" \
               f"redirect_uri={redirect_uri}&" \
               f"response_type=code&" \
               f"scope=docx:document:readonly"
    
    def exchange_code_for_token(self, code: str) -> dict:
        url = f"{self.BASE_URL}/open-apis/oauth/v3/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": settings.FEISHU_APP_ID,
            "client_secret": settings.FEISHU_APP_SECRET,
            "code": code,
        }
        response = requests.post(url, json=data)
        return response.json()
    
    def get_documents(self, access_token: str) -> list:
        headers = {"Authorization": f"Bearer {access_token}"}
        url = f"{self.BASE_URL}/open-apis/docx/v1/documents"
        response = requests.get(url, headers=headers)
        return response.json().get("data", {}).get("items", [])
    
    def get_document_content(self, access_token: str, doc_id: str) -> str:
        headers = {"Authorization": f"Bearer {access_token}"}
        url = f"{self.BASE_URL}/open-apis/docx/v1/documents/{doc_id}"
        response = requests.get(url, headers=headers)
        return response.json().get("data", {}).get("content", "")
```

### 2.12 app/services/storage.py - 数据存储

**需求：**
- 文档存储
- 文档检索
- 加密存储
- 索引管理

**关键功能：**
```python
from app.database import get_db
from app.encryption import EncryptionManager
from app.config import settings

class StorageService:
    def __init__(self):
        self.encryption = EncryptionManager(settings.ENCRYPTION_PASSWORD)
    
    def save_document(self, doc_id: str, title: str, content: str):
        conn = get_db()
        cursor = conn.cursor()
        
        encrypted_content = self.encryption.encrypt(content)
        
        cursor.execute('''
            INSERT OR REPLACE INTO documents 
            (document_id, title, content, encrypted)
            VALUES (?, ?, ?, ?)
        ''', (doc_id, title, encrypted_content, True))
        
        conn.commit()
        conn.close()
    
    def get_document(self, doc_id: int):
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM documents WHERE id = ?', (doc_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            content = self.encryption.decrypt(row['content'])
            return {
                'id': row['id'],
                'title': row['title'],
                'content': content,
                'created_time': row['created_time'],
                'modified_time': row['modified_time']
            }
        return None
    
    def get_documents(self, limit: int = 20, offset: int = 0):
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM documents 
            ORDER BY modified_time DESC 
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        documents = []
        for row in rows:
            content = self.encryption.decrypt(row['content'])
            documents.append({
                'id': row['id'],
                'title': row['title'],
                'content': content[:200] + '...',  # 摘要
                'created_time': row['created_time'],
                'modified_time': row['modified_time']
            })
        
        return documents
    
    def count_documents(self) -> int:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM documents')
        count = cursor.fetchone()[0]
        conn.close()
        return count
```

### 2.13 app/services/search.py - 搜索服务

**需求：**
- 全文搜索
- 关键词匹配
- 相关度排序
- 分页

**关键功能：**
```python
from app.database import get_db
from app.encryption import EncryptionManager
from app.config import settings

class SearchService:
    def __init__(self):
        self.encryption = EncryptionManager(settings.ENCRYPTION_PASSWORD)
    
    def search(self, query: str, limit: int = 20, offset: int = 0):
        conn = get_db()
        cursor = conn.cursor()
        
        # 使用FTS5全文搜索
        cursor.execute('''
            SELECT d.id, d.document_id, d.title, d.content, 
                   rank as score
            FROM search_index si
            JOIN documents d ON si.rowid = d.id
            WHERE search_index MATCH ?
            ORDER BY rank
            LIMIT ? OFFSET ?
        ''', (query, limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            content = self.encryption.decrypt(row['content'])
            snippet = content[:100] + '...'
            results.append({
                'id': row['id'],
                'document_id': row['document_id'],
                'title': row['title'],
                'snippet': snippet,
                'score': row['score']
            })
        
        return results
    
    def count_results(self, query: str) -> int:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM search_index 
            WHERE search_index MATCH ?
        ''', (query,))
        
        count = cursor.fetchone()[0]
        conn.close()
        return count
```

### 2.14 requirements.txt

```
fastapi==0.104.1
uvicorn==0.24.0
sqlalchemy==2.0.23
pydantic==2.5.0
pydantic-settings==2.1.0
cryptography==41.0.7
requests==2.31.0
python-dotenv==1.0.0
pytest==7.4.3
pytest-asyncio==0.21.1
```

---

## 三、前端代码生成需求

### 3.1 package.json

```json
{
  "name": "memory-capsule",
  "version": "1.0.0",
  "description": "Personal Memory Capsule - Integrate scattered memories from multiple platforms",
  "private": true,
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "axios": "^1.6.2",
    "tailwindcss": "^3.3.6",
    "react-icons": "^4.12.0"
  },
  "devDependencies": {
    "react-scripts": "5.0.1",
    "@testing-library/react": "^14.1.2",
    "@testing-library/jest-dom": "^6.1.5"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "test": "react-scripts test",
    "eject": "react-scripts eject"
  },
  "eslintConfig": {
    "extends": [
      "react-app"
    ]
  },
  "browserslist": {
    "production": [
      ">0.2%",
      "not dead",
      "not op_mini all"
    ],
    "development": [
      "last 1 chrome version",
      "last 1 firefox version",
      "last 1 safari version"
    ]
  }
}
```

### 3.2 src/App.js - 主应用

**需求：**
- 路由配置
- 认证状态管理
- 页面导航
- 响应式布局

**关键代码：**
```javascript
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import HomePage from './pages/HomePage';
import SearchPage from './pages/SearchPage';
import DetailPage from './pages/DetailPage';
import SettingsPage from './pages/SettingsPage';
import './App.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);

  useEffect(() => {
    // 检查认证状态
    const token = localStorage.getItem('access_token');
    if (token) {
      setIsAuthenticated(true);
    }
  }, []);

  return (
    <Router>
      <div className="app">
        {isAuthenticated ? (
          <div className="app-layout">
            <Header user={user} onLogout={() => setIsAuthenticated(false)} />
            <div className="app-container">
              <Sidebar />
              <main className="app-main">
                <Routes>
                  <Route path="/" element={<HomePage />} />
                  <Route path="/search" element={<SearchPage />} />
                  <Route path="/document/:id" element={<DetailPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                </Routes>
              </main>
            </div>
          </div>
        ) : (
          <Routes>
            <Route path="/login" element={<LoginPage onLogin={() => setIsAuthenticated(true)} />} />
            <Route path="*" element={<Navigate to="/login" />} />
          </Routes>
        )}
      </div>
    </Router>
  );
}

export default App;
```

### 3.3 src/components/Header.js

```javascript
import React from 'react';
import { FiLogOut, FiSettings } from 'react-icons/fi';
import './Header.css';

function Header({ user, onLogout }) {
  return (
    <header className="header">
      <div className="header-left">
        <h1 className="logo">🔱 Memory Capsule</h1>
      </div>
      <div className="header-right">
        <span className="user-name">{user?.name || 'User'}</span>
        <button className="icon-btn" title="Settings">
          <FiSettings />
        </button>
        <button className="icon-btn" onClick={onLogout} title="Logout">
          <FiLogOut />
        </button>
      </div>
    </header>
  );
}

export default Header;
```

### 3.4 src/components/Dashboard.js

```javascript
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import './Dashboard.css';

function Dashboard() {
  const [documents, setDocuments] = useState([]);
  const [stats, setStats] = useState({ total: 0, thisWeek: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      const response = await api.get('/documents?limit=10');
      setDocuments(response.data.documents);
      setStats({ total: response.data.total, thisWeek: 5 });
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="loading">Loading...</div>;

  return (
    <div className="dashboard">
      <div className="stats">
        <div className="stat-card">
          <h3>Total Documents</h3>
          <p className="stat-value">{stats.total}</p>
        </div>
        <div className="stat-card">
          <h3>This Week</h3>
          <p className="stat-value">{stats.thisWeek}</p>
        </div>
      </div>

      <div className="recent-documents">
        <h2>Recent Documents</h2>
        <div className="document-list">
          {documents.map(doc => (
            <Link key={doc.id} to={`/document/${doc.id}`} className="document-item">
              <h3>{doc.title}</h3>
              <p>{doc.snippet}</p>
              <small>{new Date(doc.modified_time).toLocaleDateString()}</small>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
```

### 3.5 src/components/SearchBar.js

```javascript
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FiSearch } from 'react-icons/fi';
import './SearchBar.css';

function SearchBar() {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();

  const handleSearch = (e) => {
    e.preventDefault();
    if (query.trim()) {
      navigate(`/search?q=${encodeURIComponent(query)}`);
    }
  };

  return (
    <form className="search-bar" onSubmit={handleSearch}>
      <input
        type="text"
        placeholder="Search your memories..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="search-input"
      />
      <button type="submit" className="search-btn">
        <FiSearch />
      </button>
    </form>
  );
}

export default SearchBar;
```

### 3.6 src/services/api.js

```javascript
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器 - 添加token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器 - 处理错误
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
```

### 3.7 src/pages/HomePage.js

```javascript
import React from 'react';
import Dashboard from '../components/Dashboard';
import SearchBar from '../components/SearchBar';
import WeeklyReview from '../components/WeeklyReview';
import './HomePage.css';

function HomePage() {
  return (
    <div className="home-page">
      <SearchBar />
      <Dashboard />
      <WeeklyReview />
    </div>
  );
}

export default HomePage;
```

### 3.8 src/pages/SearchPage.js

```javascript
import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import api from '../services/api';
import SearchBar from '../components/SearchBar';
import './SearchPage.css';

function SearchPage() {
  const [searchParams] = useSearchParams();
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const query = searchParams.get('q');

  useEffect(() => {
    if (query) {
      performSearch();
    }
  }, [query]);

  const performSearch = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/search?q=${encodeURIComponent(query)}`);
      setResults(response.data.results);
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="search-page">
      <SearchBar />
      <div className="search-results">
        <h2>Search Results for "{query}"</h2>
        {loading ? (
          <div className="loading">Searching...</div>
        ) : results.length > 0 ? (
          <div className="results-list">
            {results.map(result => (
              <div key={result.id} className="result-item">
                <h3>{result.title}</h3>
                <p>{result.snippet}</p>
                <small>Score: {result.score.toFixed(2)}</small>
              </div>
            ))}
          </div>
        ) : (
          <p className="no-results">No results found</p>
        )}
      </div>
    </div>
  );
}

export default SearchPage;
```

### 3.9 src/App.css

```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background-color: #f5f5f5;
}

.app {
  width: 100%;
  height: 100vh;
}

.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.app-container {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.app-main {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

@media (max-width: 768px) {
  .app-container {
    flex-direction: column;
  }
  
  .app-main {
    padding: 10px;
  }
}
```

---

## 四、部署配置

### 4.1 docker-compose.yml

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - FEISHU_APP_ID=cli_a949e8f4f2b85cc2
      - FEISHU_APP_SECRET=s9EHvwTkgXzlA2exwMhXFfLz3sijrE4j
      - DATABASE_PATH=/data/memory.db
    volumes:
      - ./data:/data
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:8000/api
    depends_on:
      - backend
```

### 4.2 Dockerfile (Backend)

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4.3 Dockerfile (Frontend)

```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ .

EXPOSE 3000

CMD ["npm", "start"]
```

---

## 五、测试代码

### 5.1 tests/test_auth.py

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_authorize():
    response = client.post("/api/auth/feishu/authorize", 
                          json={"redirect_uri": "http://localhost:3000/callback"})
    assert response.status_code == 200
    assert "auth_url" in response.json()

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

---

## 六、交付清单

### 代码文件
- ✅ 后端完整代码（FastAPI + SQLite + 加密）
- ✅ 前端完整代码（React + Tailwind CSS）
- ✅ 数据库脚本
- ✅ 测试代码
- ✅ Docker配置

### 文档
- ✅ README.md - 项目说明
- ✅ API文档 - 所有端点说明
- ✅ 部署指南 - 本地和Docker部署
- ✅ 开发指南 - 开发环境搭建

### 可运行性
- ✅ 本地开发环境可直接运行
- ✅ Docker一键部署
- ✅ 所有依赖已列出
- ✅ 环境变量已配置

---

## 七、代码质量标准

- ✅ 代码注释完整
- ✅ 错误处理完善
- ✅ 安全性考虑（加密、认证）
- ✅ 性能优化（索引、缓存）
- ✅ 可维护性高（模块化、清晰结构）

---

**文档完成日期：** 2026-03-27  
**版本：** 1.0  
**状态：** 待Claude Code生成代码
