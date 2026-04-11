#!/bin/bash
# DeepSeek API Key 配置脚本
# 用法: bash setup_deepseek.sh <YOUR_API_KEY>
# 或者直接在终端运行: export DEEPSEEK_API_KEY="your-key-here"

KEY="$1"
if [ -z "$KEY" ]; then
    echo "请提供 API Key:"
    echo "  bash setup_deepseek.sh <YOUR_DEEPSEEK_API_KEY>"
    exit 1
fi

# 写入 ~/.bashrc（永久生效）
if ! grep -q "DEEPSEEK_API_KEY" ~/.bashrc 2>/dev/null; then
    echo "" >> ~/.bashrc
    echo "# DeepSeek API Key (观一任务一配置)" >> ~/.bashrc
    echo "export DEEPSEEK_API_KEY=\"$KEY\"" >> ~/.bashrc
    echo "✅ 已写入 ~/.bashrc"
else
    sed -i '' "s|export DEEPSEEK_API_KEY=.*|export DEEPSEEK_API_KEY=\"$KEY\"|" ~/.bashrc
    echo "✅ 已更新 ~/.bashrc"
fi

# 立即生效（当前终端）
export DEEPSEEK_API_KEY="$KEY"
echo "✅ 当前会话 Key 已设置"
echo "验证: ${DEEPSEEK_API_KEY:0:8}..."
