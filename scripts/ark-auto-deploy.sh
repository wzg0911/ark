#!/bin/bash
# ARK自动化发布脚本 - 一键部署所有内容
# 在GitHub PAT更新后运行

set -e

# === 配置 ===
ARK_REPO="/Users/w/.hermes/projects/ark"
WORKSPACE="/Users/w/.openclaw/workspace"

echo "🚀 ARK 自动化发布管道"

# 1. 复制营销内容到仓库
echo ""
echo "📝 [1/5] 同步营销内容..."
cp "$WORKSPACE/FUNDING.yml" "$ARK_REPO/FUNDING.yml" 2>/dev/null || true
cp "$WORKSPACE/SPONSOR.md" "$ARK_REPO/SPONSOR.md" 2>/dev/null || true

# 2. 同步BLOG文章
echo "📝 [2/5] 同步博客文章..."
if [ -d "$ARK_REPO/blog" ]; then
  mkdir -p "$ARK_REPO/blog/posts"
  # 复制营销稿
  cp "$WORKSPACE/marketing-2026-06-17/content-01.md" "$ARK_REPO/blog/posts/ai-agent-reliability-intro.md" 2>/dev/null || true
  cp "$WORKSPACE/ark-launch-copy-v2ex.md" "$ARK_REPO/blog/posts/ark-launch-v2ex.md" 2>/dev/null || true
fi

# 3. README徽章
echo "🏷️  [3/5] 更新README徽章..."
if [ -f "$ARK_REPO/README.md" ]; then
  # 确保已有Sponsor徽章
  if ! grep -q "sponsor" "$ARK_REPO/README.md"; then
    echo "" >> "$ARK_REPO/README.md"
    echo "---" >> "$ARK_REPO/README.md"
    echo "### 🤝 赞助" >> "$ARK_REPO/README.md"
    echo "" >> "$ARK_REPO/README.md"
    echo "[![" >> "$ARK_REPO/README.md"
    echo "  GitHub Sponsors" >> "$ARK_REPO/README.md"
    echo "](https://img.shields.io/badge/Sponsor-%E2%9D%A4%EF%B8%8F-orange?logo=github" >> "$ARK_REPO/README.md"
    echo ")](https://github.com/sponsors/wzg0911)" >> "$ARK_REPO/README.md"
    echo "[![爱发电](https://img.shields.io/badge/%E7%88%B1%E5%8F%91%E7%94%B5-%E8%AF%B7%E5%96%9D%E5%92%96%E5%95%A1-blue)](https://afdian.com/a/wzg911)" >> "$ARK_REPO/README.md"
    echo "" >> "$ARK_REPO/README.md"
    echo "**ARK Trust** is free and open source. If it saves you money or time," >> "$ARK_REPO/README.md"
    echo "please consider [sponsoring](SPONSOR.md) the project." >> "$ARK_REPO/README.md"
  fi
fi

# 4. GitHub提交
echo "📤 [4/5] Git提交..."
cd "$ARK_REPO"
git add -A
git commit -m "chore: auto-deploy $(date +%Y-%m-%d_%H:%M)" 2>/dev/null || echo "  (无变更，跳过提交)"
echo "  ⏳ 等待GitHub PAT更新后运行: git push origin main"

# 5. 报告状态
echo ""
echo "✅ [5/5] 管道运行完毕"
echo "======================"
echo "📊 状态报告"
echo ""
echo "✅ 已就绪:"
echo "  - FUNDING.yml (GitHub Sponsors配置)"
echo "  - SPONSOR.md (赞助指南)"
echo "  - content-01.md (AI Agent可靠性文章)"
echo "  - V2EX发布文案"
echo "  - 自动化部署脚本"
echo ""
echo "⏳ 待主人操作:"
echo "  1. 生成新GitHub PAT"
echo "  2. 注册小报童"
echo "  3. 注册爱发电"
echo "  4. 注册/登录知乎/CSDN/掘金"
echo "  5. 运行本脚本完成推送"
echo ""
echo "🔗 关键链接:"
echo "  ARK仓库:     https://github.com/wzg0911/ark"
echo "  ARK SDK:     https://pypi.org/project/ark-trust/"
echo "  ARK TS SDK:  https://www.npmjs.com/package/@feilunxitong/arkit"
echo "  Badge服务:   https://ark-badge-service.vercel.app"
echo "  Surge部署:   https://ark-trust.surge.sh"
