#!/bin/bash
# ==============================================================================
# Hermes Agent Cloud Studio 部署脚本
# ==============================================================================
# 适用环境：Cloud Studio (Linux)
# API配置：阿里云百炼国际站 (custom provider)
# 更新时间：2026-04-12
# ==============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ==============================================================================
# 配置区域（按需修改）
# ==============================================================================
export API_KEY="sk-49fd2bf8d54d4dc294d0afab54d98db3"
export BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
export DEFAULT_MODEL="qwen2.5-7b-instruct"
export INSTALL_DIR="$HOME/.hermes"
export HERMES_DIR="$INSTALL_DIR/hermes-agent"

# ==============================================================================
# Step 1: 环境检查
# ==============================================================================
echo ""
log_info "=== Step 1: 环境检查 ==="
python3 --version
git --version
echo ""

# ==============================================================================
# Step 2: 安装 uv (快速Python包管理器)
# ==============================================================================
echo ""
log_info "=== Step 2: 安装 uv ==="

if command -v uv &>/dev/null; then
    log_info "uv 已安装: $(uv --version)"
else
    log_info "安装 uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.local/bin/env 2>/dev/null || true
    export PATH="$HOME/.local/bin:$PATH"
    uv --version
fi
echo ""

# ==============================================================================
# Step 3: 克隆 Hermes 仓库 (Gitee镜像)
# ==============================================================================
echo ""
log_info "=== Step 3: 克隆 Hermes 仓库 ==="

if [ -d "$HERMES_DIR" ]; then
    log_warn "Hermes 目录已存在，跳过克隆"
else
    git clone --recurse-submodules https://gitee.com/bsice/hermes-agent.git "$HERMES_DIR"
fi
echo ""

# ==============================================================================
# Step 4: 创建虚拟环境并安装依赖
# ==============================================================================
echo ""
log_info "=== Step 4: 创建虚拟环境并安装依赖 ==="

cd "$HERMES_DIR"

# 使用 uv 创建虚拟环境 (Python 3.11)
uv venv venv --python 3.11

# 安装依赖
uv pip install -e ".[all]"

echo ""

# ==============================================================================
# Step 5: 配置
# ==============================================================================
echo ""
log_info "=== Step 5: 配置 Hermes ==="

mkdir -p "$INSTALL_DIR"

# 写入配置文件
cat > "$INSTALL_DIR/config.yaml" << EOF
model:
  provider: custom
  default: $DEFAULT_MODEL
  base_url: $BASE_URL
  api_key: $API_KEY

max_turns: 90

terminal:
  backend: local
  cwd: .
  timeout: 180

compression:
  enabled: true
  threshold: 0.5
  target_ratio: 0.2
EOF

log_info "配置文件已写入: $INSTALL_DIR/config.yaml"
echo ""

# ==============================================================================
# Step 6: 验证安装
# ==============================================================================
echo ""
log_info "=== Step 6: 验证安装 ==="

# 设置环境变量
export PATH="$HERMES_DIR/venv/bin:$HOME/.local/bin:$PATH"

# 创建hermes别名
echo "alias hermes='$HERMES_DIR/venv/bin/hermes'" >> $HOME/.bashrc

# 加载配置
source $HOME/.bashrc 2>/dev/null || true

# 验证hermes命令
if command -v hermes &>/dev/null; then
    log_info "✅ hermes 命令已就绪"
    hermes --version 2>/dev/null || hermes --help 2>/dev/null | head -3
else
    log_info "hermes 命令路径: $HERMES_DIR/venv/bin/hermes"
    $HERMES_DIR/venv/bin/hermes --version 2>/dev/null || echo "验证命令..."
fi

echo ""

# ==============================================================================
# 完成
# ==============================================================================
echo ""
log_info "=========================================="
log_info "  Hermes Agent 安装完成！"
log_info "=========================================="
echo ""
log_info "下一步操作："
echo "  1. 重新加载配置: source ~/.bashrc"
echo "  2. 启动对话: hermes"
echo "  3. 配置飞书网关: hermes gateway setup"
echo ""
log_info "配置文件位置: $INSTALL_DIR/config.yaml"
log_info "Hermes目录: $HERMES_DIR"
echo ""
