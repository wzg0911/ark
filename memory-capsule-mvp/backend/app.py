#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个人记忆胶囊 MVP - 后端服务
零依赖版本（仅使用Python3标准库）
"""

import json
import sqlite3
import hashlib
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
import base64
import secrets

# ============ 配置 ============
DATABASE_PATH = "./data/memory.db"
PORT = 8000
HOST = "0.0.0.0"

# ============ 数据库初始化 ============
def init_db():
    """初始化数据库"""
    os.makedirs("./data", exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # 创建documents表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source TEXT DEFAULT 'feishu'
        )
    ''')
    
    # 创建用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            access_token TEXT,
            created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建搜索历史表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            result_count INTEGER,
            created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ 数据库初始化完成")

# ============ 模拟数据 ============
def insert_demo_data():
    """插入演示数据"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # 检查是否已有数据
    cursor.execute("SELECT COUNT(*) FROM documents")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return
    
    demo_docs = [
        ("doc_001", "元神AI项目入口技术验证报告", "这是一份关于元神AI项目的技术验证报告，包含了完整的技术架构设计、功能需求、API设计等内容。项目采用React + FastAPI + SQLite的技术栈，支持飞书OAuth认证、数据加密存储、全文搜索等功能。", "2026-03-25"),
        ("doc_002", "元神AI融资计划书（BP）", "这是元神AI的融资计划书，包含了项目概述、市场分析、商业模式、融资需求等内容。项目目标市场规模为60亿元，预计6个月内实现盈亏平衡。", "2026-03-26"),
        ("doc_003", "个人记忆胶囊MVP开发计划", "MVP开发计划包含了6周的详细开发里程碑，包括架构设计、核心功能开发、前端开发、测试优化等阶段。", "2026-03-27"),
        ("doc_004", "飞书API集成指南", "详细的飞书API集成指南，包含OAuth认证流程、文档获取API、权限管理等内容。", "2026-03-24"),
        ("doc_005", "数据加密和隐私保护方案", "详细的数据加密方案，采用AES-256-CBC加密算法，PBKDF2密钥派生，确保用户数据的安全性和隐私性。", "2026-03-23"),
        ("doc_006", "用户界面设计规范", "完整的UI设计规范，包含色彩方案、字体选择、组件设计、响应式布局等内容。", "2026-03-22"),
        ("doc_007", "性能优化方案", "性能优化方案包括数据库索引优化、API缓存、前端代码分割等内容。", "2026-03-21"),
        ("doc_008", "测试计划和质量保证", "完整的测试计划，包括单元测试、集成测试、性能测试、安全测试等内容。", "2026-03-20"),
    ]
    
    for doc_id, title, content, date in demo_docs:
        cursor.execute('''
            INSERT INTO documents (document_id, title, content, created_time, modified_time)
            VALUES (?, ?, ?, ?, ?)
        ''', (doc_id, title, content, date, date))
    
    conn.commit()
    conn.close()
    print(f"✅ 插入{len(demo_docs)}条演示数据")

# ============ API处理器 ============
class APIHandler(BaseHTTPRequestHandler):
    """HTTP请求处理器"""
    
    def do_GET(self):
        """处理GET请求"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)
        
        # 路由处理
        if path == "/api/health":
            self.send_json({"status": "ok", "timestamp": datetime.now().isoformat()})
        
        elif path == "/api/documents":
            self.handle_list_documents(query_params)
        
        elif path.startswith("/api/documents/"):
            doc_id = path.split("/")[-1]
            self.handle_get_document(doc_id)
        
        elif path == "/api/search":
            query = query_params.get("q", [""])[0]
            self.handle_search(query)
        
        elif path == "/api/weekly-review":
            self.handle_weekly_review()
        
        elif path == "/api/stats":
            self.handle_stats()
        
        elif path == "/":
            self.send_file("./frontend/index.html", "text/html")
        
        elif path.endswith(".js"):
            self.send_file(f"./frontend{path}", "application/javascript")
        
        elif path.endswith(".css"):
            self.send_file(f"./frontend{path}", "text/css")
        
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        """处理POST请求"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # 读取请求体
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        # 路由处理
        if path == "/api/auth/feishu/authorize":
            self.handle_feishu_authorize(data)
        
        elif path == "/api/documents/sync":
            self.handle_sync_documents(data)
        
        else:
            self.send_error(404, "Not Found")
    
    def handle_list_documents(self, query_params):
        """获取文档列表"""
        limit = int(query_params.get("limit", ["20"])[0])
        offset = int(query_params.get("offset", ["0"])[0])
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # 获取总数
        cursor.execute("SELECT COUNT(*) FROM documents")
        total = cursor.fetchone()[0]
        
        # 获取分页数据
        cursor.execute('''
            SELECT id, document_id, title, content, created_time, modified_time
            FROM documents
            ORDER BY modified_time DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        documents = []
        for row in rows:
            doc_id, doc_id_str, title, content, created, modified = row
            documents.append({
                "id": doc_id,
                "document_id": doc_id_str,
                "title": title,
                "snippet": content[:100] + "..." if len(content) > 100 else content,
                "created_time": created,
                "modified_time": modified
            })
        
        self.send_json({
            "total": total,
            "limit": limit,
            "offset": offset,
            "documents": documents
        })
    
    def handle_get_document(self, doc_id):
        """获取单个文档"""
        try:
            doc_id_int = int(doc_id)
        except:
            self.send_error(400, "Invalid document ID")
            return
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, document_id, title, content, created_time, modified_time
            FROM documents
            WHERE id = ?
        ''', (doc_id_int,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            self.send_error(404, "Document not found")
            return
        
        doc_id_int, doc_id_str, title, content, created, modified = row
        self.send_json({
            "id": doc_id_int,
            "document_id": doc_id_str,
            "title": title,
            "content": content,
            "created_time": created,
            "modified_time": modified
        })
    
    def handle_search(self, query):
        """搜索文档"""
        if not query:
            self.send_json({"total": 0, "results": []})
            return
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # 简单的LIKE搜索
        search_term = f"%{query}%"
        cursor.execute('''
            SELECT id, document_id, title, content
            FROM documents
            WHERE title LIKE ? OR content LIKE ?
            ORDER BY modified_time DESC
        ''', (search_term, search_term))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            doc_id, doc_id_str, title, content = row
            # 找到匹配的片段
            if query.lower() in title.lower():
                snippet = title
            else:
                idx = content.lower().find(query.lower())
                if idx >= 0:
                    start = max(0, idx - 50)
                    end = min(len(content), idx + len(query) + 50)
                    snippet = "..." + content[start:end] + "..."
                else:
                    snippet = content[:100] + "..."
            
            results.append({
                "id": doc_id,
                "document_id": doc_id_str,
                "title": title,
                "snippet": snippet,
                "score": 0.95
            })
        
        self.send_json({
            "total": len(results),
            "results": results
        })
    
    def handle_weekly_review(self):
        """周回顾"""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # 获取过去7天的文档
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        cursor.execute('''
            SELECT id, document_id, title, content, modified_time
            FROM documents
            WHERE modified_time >= ?
            ORDER BY modified_time DESC
        ''', (week_ago,))
        
        rows = cursor.fetchall()
        conn.close()
        
        documents = []
        for row in rows:
            doc_id, doc_id_str, title, content, modified = row
            documents.append({
                "id": doc_id,
                "title": title,
                "snippet": content[:100] + "...",
                "modified_time": modified
            })
        
        self.send_json({
            "week": f"{(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}",
            "total_documents": len(documents),
            "documents": documents
        })
    
    def handle_stats(self):
        """获取统计信息"""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM documents")
        total = cursor.fetchone()[0]
        
        # 本周新增
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        cursor.execute("SELECT COUNT(*) FROM documents WHERE created_time >= ?", (week_ago,))
        this_week = cursor.fetchone()[0]
        
        conn.close()
        
        self.send_json({
            "total_documents": total,
            "this_week": this_week,
            "last_sync": datetime.now().isoformat()
        })
    
    def handle_feishu_authorize(self, data):
        """飞书授权"""
        # 模拟授权流程
        user_id = f"user_{secrets.token_hex(8)}"
        access_token = secrets.token_urlsafe(32)
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, access_token)
            VALUES (?, ?)
        ''', (user_id, access_token))
        conn.commit()
        conn.close()
        
        self.send_json({
            "success": True,
            "user_id": user_id,
            "access_token": access_token,
            "message": "✅ 飞书授权成功！已自动同步您的文档。"
        })
    
    def handle_sync_documents(self, data):
        """同步文档"""
        self.send_json({
            "success": True,
            "synced_count": 8,
            "message": "✅ 同步完成！新增8份文档。"
        })
    
    def send_json(self, data):
        """发送JSON响应"""
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    
    def send_file(self, filepath, content_type):
        """发送文件"""
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404, "File not found")
    
    def log_message(self, format, *args):
        """自定义日志"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {format % args}")

# ============ 主程序 ============
if __name__ == "__main__":
    print("🔱 个人记忆胶囊 MVP - 后端启动")
    print("=" * 50)
    
    # 初始化数据库
    init_db()
    insert_demo_data()
    
    # 启动服务器
    server = HTTPServer((HOST, PORT), APIHandler)
    print(f"✅ 服务器运行在 http://{HOST}:{PORT}")
    print("按 Ctrl+C 停止服务器")
    print("=" * 50)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 服务器已停止")
        server.server_close()
