#!/bin/bash

# 个人记忆胶囊 MVP - 启动脚本
# 零依赖版本（仅需Python3）

echo "🔱 个人记忆胶囊 MVP - 启动"
echo "================================"

# 检查Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误：未找到Python3"
    echo "请先安装Python3"
    exit 1
fi

echo "✅ Python3 已安装: $(python3 --version)"

# 创建数据目录
mkdir -p ./data

# 启动后端服务
echo ""
echo "🚀 启动后端服务..."
cd backend
python3 app.py &
BACKEND_PID=$!
echo "✅ 后端服务已启动 (PID: $BACKEND_PID)"

# 等待后端启动
sleep 2

# 打开浏览器
echo ""
echo "🌐 打开浏览器..."
if command -v open &> /dev/null; then
    open http://localhost:8000
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8000
else
    echo "请手动打开浏览器访问: http://localhost:8000"
fi

echo ""
echo "================================"
echo "✅ 应用已启动！"
echo "📱 访问地址: http://localhost:8000"
echo "🛑 按 Ctrl+C 停止服务"
echo "================================"

# 等待后端进程
wait $BACKEND_PID
