#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""元神AI背景图生成v2 - 按优化指南描述参数精确复刻"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os, math, random
from PIL import Image, ImageDraw, ImageFilter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

random.seed(99)
W, H = 3840, 2160

# ═══════════════════════════════════════════════════════
# 背景一：封面/封底
# 深邃宇宙 + 星云暗纹 + 底部向上鎏金光芒 + 星光颗粒
# ═══════════════════════════════════════════════════════
def make_bg1():
    print("背景一（封面封底）...")
    DPI = 150
    fig = plt.figure(figsize=(W/DPI, H/DPI), dpi=DPI)
    fig.patch.set_facecolor('#020509')
    ax = fig.add_axes([0,0,1,1])
    ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis('off')
    ax.set_facecolor('#020509')

    # 星云：用渐变椭圆叠加
    nebula_color_strs = ['#12081f','#1a0d30','#0d0520','#1a0a35','#150830','#1e0d40','#0a1025','#1a0830']
    for i in range(15):
        cx = random.uniform(0.1, 0.9)
        cy = random.uniform(0.2, 0.7)
        rx = random.uniform(0.15, 0.35)
        ry = random.uniform(0.08, 0.2)
        c2 = random.choice(nebula_color_strs)
        alpha_v = max(0.05, 0.4 - i*0.02)
        for scale in [1.0, 0.75, 0.5]:
            ell = patches.Ellipse((cx, cy), rx*2*scale, ry*2*scale,
                                  facecolor=c2, alpha=alpha_v, edgecolor='none', zorder=1)
            ax.add_patch(ell)

    # 底部向上鎏金光芒
    grad_data = np.zeros((H, W, 3))
    for y in range(H):
        t = max(0, (H - y) / (H * 0.55))
        intensity = t ** 0.6
        r = int(180 + 75 * intensity)
        g = int(140 + 55 * intensity)
        b = int(10 + 15 * intensity)
        # 横向中心衰减
        for x in range(W):
            cx2 = abs(x - W/2) / (W/2)
            att = max(0, 1 - cx2 ** 1.5)
            grad_data[y, x] = [
                min(255, int(r * att * intensity)),
                min(255, int(g * att * intensity)),
                min(255, int(b * att * intensity)),
            ]
    # 模糊光芒用PIL处理
    grad_img_data = (np.clip(grad_data, 0, 255) / 255).astype(np.float32)
    # 用matplotlib imshow的 interpolation
    ax.imshow(grad_img_data, extent=[0,1,0,1], aspect='auto', zorder=2,
              alpha=0.7, origin='lower', interpolation='gaussian')

    # 中心金色光晕
    grad2 = LinearSegmentedColormap.from_list('glow',
        ['#000000','#3a2800','#7a5500','#d4af37','#ffe066'])
    gx, gy = 0.5, 0.42
    for frac in [0.3, 0.5, 0.7, 1.0]:
        ell = patches.Ellipse((gx, gy), 0.28*frac, 0.12*frac,
                             facecolor='#c8a030', alpha=0.15*(1-frac*0.5),
                             edgecolor='none', zorder=3)
        ax.add_patch(ell)

    # 星光颗粒（极小亮点）
    np.random.seed(42)
    stars_x = np.random.uniform(0, 1, 3000)
    stars_y = np.random.uniform(0, 1, 3000)
    stars_s = np.random.uniform(0.0003, 0.001, 3000)
    stars_b = np.random.uniform(0.3, 1.0, 3000)
    for x, y, s, b in zip(stars_x, stars_y, stars_s, stars_b):
        c = int(180 + 75*b)
        ell = patches.Circle((x, y), s, facecolor='#ffffff', alpha=b, zorder=4)
        ax.add_patch(ell)

    fig.savefig('/tmp/bg1_raw.png', dpi=DPI,
                bbox_inches=0, pad_inches=0,
                facecolor='#020509')
    plt.close(fig)
    # 转换为RGB保存
    img = Image.open('/tmp/bg1_raw.png').convert('RGB')
    # 进一步模糊融合
    img = img.filter(ImageFilter.GaussianBlur(radius=2))
    out = "/Users/w/.openclaw/workspace/bg1_封面封底.png"
    img.save(out, optimize=True)
    sz = os.path.getsize(out)
    print(f"✅ 背景一完成 {sz//1024//1024:.1f}MB")
    return out

# ═══════════════════════════════════════════════════════
# 背景二：目录页
# 黑金奢雅 + 左下到右上鎏金线条汇聚
# ═══════════════════════════════════════════════════════
def make_bg2():
    print("背景二（目录页）...")
    DPI = 150
    fig = plt.figure(figsize=(W/DPI, H/DPI), dpi=DPI)
    fig.patch.set_facecolor('#040410')
    ax = fig.add_axes([0,0,1,1])
    ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis('off')
    ax.set_facecolor('#040410')

    # 汇聚线条（左下→右上）
    sx, sy = 0.12, 0.12
    ex, ey = 0.62, 0.38
    dx, dy = ex - sx, ey - sy
    L = math.sqrt(dx**2 + dy**2)
    nx, ny = -dy/L, dx/L

    for i in range(35):
        off = (i - 17) * 0.012
        osx = sx + nx * off
        osy = sy + ny * off
        oex = ex + nx * off * 0.4
        oey = ey + ny * off * 0.4
        inten = max(0.2, 1.0 - abs(i - 17) * 0.045)
        lw = max(0.3, 2.5 - abs(i - 17) * 0.08)
        ax.plot([osx, oex], [osy, oey],
                color=(0.72 + inten*0.2, 0.52 + inten*0.15, 0.05),
                linewidth=lw, alpha=inten*0.9, zorder=2)

    # 汇聚点辉光
    for r_frac in [0.12, 0.09, 0.06, 0.04, 0.02]:
        ell = patches.Ellipse((ex, ey), r_frac, r_frac*0.5,
                              facecolor='#d4af37', alpha=0.12*(1-r_frac*3),
                              edgecolor='none', zorder=3)
        ax.add_patch(ell)
    ell_core = patches.Ellipse((ex, ey), 0.015, 0.007,
                               facecolor='#ffe066', alpha=0.9, edgecolor='none', zorder=4)
    ax.add_patch(ell_core)

    # 星点散布
    np.random.seed(88)
    sx2 = np.random.uniform(0,1,1200)
    sy2 = np.random.uniform(0,1,1200)
    sb = np.random.uniform(0.2, 0.8, 1200)
    for x, y, b in zip(sx2, sy2, sb):
        c = (min(1.0, 0.5+b*0.5), min(1.0, 0.4+b*0.3), 0.1)
        ell = patches.Circle((x,y), 0.0005*(1+b), facecolor=c, alpha=b*0.7, zorder=5)
        ax.add_patch(ell)

    fig.savefig('/tmp/bg2_raw.png', dpi=DPI,
                bbox_inches=0, pad_inches=0, facecolor='#040410')
    plt.close(fig)
    img = Image.open('/tmp/bg2_raw.png').convert('RGB')
    img = img.filter(ImageFilter.GaussianBlur(radius=1))
    out = "/Users/w/.openclaw/workspace/bg2_目录页.png"
    img.save(out, optimize=True)
    sz = os.path.getsize(out)
    print(f"✅ 背景二完成 {sz//1024//1024:.1f}MB")
    return out

# ═══════════════════════════════════════════════════════
# 背景三：内容页（通用）
# 深黑微蓝纹理 + 边缘鎏金细线 + 四角L型装饰
# ═══════════════════════════════════════════════════════
def make_bg3():
    print("背景三（内容页）...")
    DPI = 150
    fig = plt.figure(figsize=(W/DPI, H/DPI), dpi=DPI)
    fig.patch.set_facecolor('#030510')
    ax = fig.add_axes([0,0,1,1])
    ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis('off')
    ax.set_facecolor('#030510')

    # 深蓝纹理（模糊椭圆）
    np.random.seed(77)
    for _ in range(20):
        cx = np.random.uniform(0.05, 0.95)
        cy = np.random.uniform(0.05, 0.95)
        rx = np.random.uniform(0.12, 0.3)
        ry = np.random.uniform(0.06, 0.15)
        ell = patches.Ellipse((cx,cy), rx*2, ry*2,
                              facecolor='#0a1535', alpha=0.6, edgecolor='none', zorder=1)
        ax.add_patch(ell)

    # 边缘鎏金细线（四边渐变淡出）
    M = 0.06
    # 顶边
    for i in range(30):
        y_top = 1 - i/30 * M
        alpha = (1 - i/30) * 0.8
        lw = max(0.3, 2.0 - i*0.05)
        ax.plot([0,1],[y_top,y_top], color=(0.72,0.55,0.08),
                linewidth=lw, alpha=alpha, zorder=2)
    # 底边
    for i in range(30):
        y_bot = i/30 * M
        alpha = (1 - i/30) * 0.8
        lw = max(0.3, 2.0 - i*0.05)
        ax.plot([0,1],[y_bot,y_bot], color=(0.72,0.55,0.08),
                linewidth=lw, alpha=alpha, zorder=2)
    # 左边
    for i in range(30):
        x_left = i/30 * M
        alpha = (1 - i/30) * 0.7
        lw = max(0.3, 2.0 - i*0.05)
        ax.plot([x_left,x_left],[0,1], color=(0.72,0.55,0.08),
                linewidth=lw, alpha=alpha, zorder=2)
    # 右边
    for i in range(30):
        x_right = 1 - i/30 * M
        alpha = (1 - i/30) * 0.7
        lw = max(0.3, 2.0 - i*0.05)
        ax.plot([x_right,x_right],[0,1], color=(0.72,0.55,0.08),
                linewidth=lw, alpha=alpha, zorder=2)

    # 四角L型金色装饰
    CL = 0.065  # 角线长度比例
    for (x0, y0, dx, dy) in [(0,0,1,1),(1,0,-1,1),(0,1,1,-1),(1,1,-1,-1)]:
        xs = [x0, x0 + dx*CL] if dx > 0 else [x0 + dx*CL, x0]
        ys = [y0, y0 + dy*CL] if dy > 0 else [y0 + dy*CL, y0]
        for i in range(20):
            t = i/20
            x1 = x0 + dx * CL * t
            y1 = y0
            x2 = x0
            y2 = y0 + dy * CL * t
            if dx < 0: x1, x2 = x0 + dx*CL, x0
            if dy < 0: y1, y2 = y0 + dy*CL, y0
            alpha = (1 - t**0.6) * 0.95
            lw = max(0.5, 2.5 - t*40)
            # 横线
            x_start = x0 if dx > 0 else x0 + dx*CL
            x_end = x0 + dx*CL if dx > 0 else x0
            ax.plot([x_start, x_start + (x_end-x_start)*t],
                    [y0, y0], color=(0.75,0.58,0.1),
                    linewidth=lw, alpha=alpha, zorder=3)
            ax.plot([x0, x0], [y0, y0 + dy*CL*t],
                    color=(0.75,0.58,0.1), linewidth=lw, alpha=alpha, zorder=3)

    fig.savefig('/tmp/bg3_raw.png', dpi=DPI,
                bbox_inches=0, pad_inches=0, facecolor='#030510')
    plt.close(fig)
    img = Image.open('/tmp/bg3_raw.png').convert('RGB')
    img = img.filter(ImageFilter.GaussianBlur(radius=1))
    out = "/Users/w/.openclaw/workspace/bg3_内容页.png"
    img.save(out, optimize=True)
    sz = os.path.getsize(out)
    print(f"✅ 背景三完成 {sz//1024//1024:.1f}MB")
    return out


if __name__ == "__main__":
    print("=" * 50)
    print("元神AI背景图 v2（matplotlib+PIL精确复刻版）")
    print("分辨率: 3840×2160")
    print("=" * 50)
    import time
    t0 = time.time()
    out1 = make_bg1()
    out2 = make_bg2()
    out3 = make_bg3()
    print(f"\n✅ 全部完成，耗时 {time.time()-t0:.1f}s")
    print(f"背景一: {out1}")
    print(f"背景二: {out2}")
    print(f"背景三: {out3}")
