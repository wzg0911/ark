#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""元神AI三张背景图 - 高效版（纯PIL，无逐像素循环）"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image, ImageDraw, ImageFilter
import random, math, os

random.seed(42)
W, H = 3840, 2160

# ─── 高效工具 ───────────────────────────────────────────

def overlay(base, top, alpha=1.0):
    """加法混合两张RGB图"""
    out = base.copy()
    blended = Image.blend(top.convert('RGB'), base.convert('RGB'), 1 - alpha)
    out.paste(blended, (0, 0))
    return out

def add_overlay(base, overlay_img, alpha=1.0):
    """叠加overlay_img到底图，alpha控制强度"""
    tmp = Image.new('RGB', base.size, (0, 0, 0))
    tmp.paste(overlay_img, (0, 0))
    blur = tmp.filter(ImageFilter.GaussianBlur(0))
    return Image.blend(base, tmp, alpha)

# ─── 背景一：封面/封底 ──────────────────────────────────
# 关键词：深邃宇宙 + 星云 + 底部向上鎏金光芒 + 星光颗粒

def make_bg1():
    print("背景一：封面封底...", flush=True)
    t0 = os.times().elapsed

    # 底层极深蓝黑
    bg = Image.new('RGB', (W, H), (3, 5, 14))

    # 星云：用多个模糊椭圆
    nebula = Image.new('RGB', (W, H), (0, 0, 0))
    nd = ImageDraw.Draw(nebula)
    nebula_data = [
        (W//3, H//3, W//3, H//3, (22, 10, 45)),
        (W*2//3, H//2, W//4, H//2, (15, 7, 32)),
        (W//2, H*2//3, W//3, H//3, (28, 14, 55)),
        (W*3//4, H//4, W//5, H//3, (10, 6, 26)),
        (W//6, H*3//4, W//4, H//3, (18, 11, 40)),
    ]
    for cx, cy, rw, rh, col in nebula_data:
        nd.ellipse([cx-rw, cy-rh, cx+rw, cy+rh], fill=col)
    nebula = nebula.filter(ImageFilter.GaussianBlur(120))
    bg = Image.blend(bg, nebula, 0.75)

    # 星光颗粒
    stars = Image.new('L', (W, H), 0)
    sd = ImageDraw.Draw(stars)
    for _ in range(5000):
        sx = random.randint(0, W-1)
        sy = random.randint(0, H-1)
        b = random.randint(80, 255)
        sz = random.choice([1,1,1,2])
        sd.ellipse([sx, sy, sx+sz, sy+sz], fill=b)
    stars = stars.filter(ImageFilter.GaussianBlur(1))
    stars_rgb = Image.merge('RGB', [stars, stars, stars])
    bg = Image.blend(bg, stars_rgb, 0.45)

    # 底部鎏金光芒：画一个垂直渐变条再模糊
    glow_bar = Image.new('RGB', (W, H), (0, 0, 0))
    gbd = ImageDraw.Draw(glow_bar)
    bh = H * 5 // 7  # 光芒高度
    for x in range(W):
        dist = abs(x - W//2) / (W//2)
        a = int(220 * max(0, 1 - dist ** 1.2))
        gbd.line([(x, H-bh), (x, H)], fill=(200+a//4, 160+a//5, 20), width=1)
    glow_bar = glow_bar.filter(ImageFilter.GaussianBlur(60))
    # 叠加光芒
    bg = Image.blend(bg, glow_bar, 0.65)

    # 中心额外金色光晕（汇聚点）
    center_glow = Image.new('RGB', (W, H), (0, 0, 0))
    cgd = ImageDraw.Draw(center_glow)
    for r in range(400, 0, -1):
        t = r / 400
        a = int(80 * (1 - t ** 1.5))
        cgd.ellipse([W//2-r, H*2//5-r//3, W//2+r, H*2//5+r//3],
                    fill=(200+a//2, 160+a//3, 0))
    center_glow = center_glow.filter(ImageFilter.GaussianBlur(80))
    bg = Image.blend(bg, center_glow, 0.5)

    out = "/Users/w/.openclaw/workspace/bg1_封面封底.png"
    bg.save(out, optimize=True)
    sz = os.path.getsize(out)
    print(f"✅ 背景一完成 {sz//1024//1024}MB ({os.times().elapsed-t0:.1f}s)", flush=True)
    return out

# ─── 背景二：目录页 ────────────────────────────────────
# 关键词：黑金奢雅 + 左下到右上金线汇聚

def make_bg2():
    print("背景二：目录页...", flush=True)
    t0 = os.times().elapsed

    bg = Image.new('RGB', (W, H), (4, 4, 13))

    # 汇聚线条（25条平行线，左下→右上）
    lines = Image.new('RGB', (W, H), (0, 0, 0))
    ld = ImageDraw.Draw(lines)

    sx, sy = W//7, int(H * 0.88)
    ex, ey = int(W * 0.6), int(H * 0.32)
    dx, dy = ex - sx, ey - sy
    L = math.sqrt(dx**2 + dy**2)
    nx, ny = -dy / L, dx / L  # 法向量

    for i in range(25):
        off = (i - 12) * 20
        osx, osy = sx + nx*off, sy + ny*off
        oex, oey = ex + nx*off*0.4, ey + ny*off*0.4
        inten = max(30, 200 - abs(off) * 4)
        col = (min(255, 165+inten//4), min(255, 125+inten//5), 0)
        w = max(1, 4 - abs(off)//20)
        ld.line([(int(osx), int(osy)), (int(oex), int(oey))],
                fill=col, width=w)

    # 汇聚点辉光
    gx, gy = int(W*0.58), int(H*0.35)
    for r in range(120, 0, -1):
        t = r / 120
        a = int(90 * (1 - t**1.5))
        ld.ellipse([gx-r, gy-r//2, gx+r, gy+r//2],
                   fill=(205+a//2, 168+a//3, 0))

    lines = lines.filter(ImageFilter.GaussianBlur(12))
    bg = Image.blend(bg, lines, 0.85)

    # 星点
    stars = Image.new('L', (W, H), 0)
    sd = ImageDraw.Draw(stars)
    for _ in range(1500):
        sx = random.randint(0, W-1)
        sy = random.randint(0, H-1)
        b = random.randint(70, 220)
        sd.point((sx, sy), fill=b)
    stars = stars.filter(ImageFilter.GaussianBlur(1))
    stars_rgb = Image.merge('RGB', [stars, stars, stars])
    bg = Image.blend(bg, stars_rgb, 0.3)

    out = "/Users/w/.openclaw/workspace/bg2_目录页.png"
    bg.save(out, optimize=True)
    sz = os.path.getsize(out)
    print(f"✅ 背景二完成 {sz//1024//1024}MB ({os.times().elapsed-t0:.1f}s)", flush=True)
    return out

# ─── 背景三：内容页 ────────────────────────────────────
# 关键词：深黑微蓝 + 边缘鎏金细线 + 四角L型装饰

def make_bg3():
    print("背景三：内容页...", flush=True)
    t0 = os.times().elapsed

    bg = Image.new('RGB', (W, H), (3, 6, 16))

    # 深蓝纹理
    tex = Image.new('RGB', (W, H), (0, 0, 0))
    td = ImageDraw.Draw(tex)
    for _ in range(18):
        cx = random.randint(0, W)
        cy = random.randint(0, H)
        rw = random.randint(W//6, W//2)
        rh = random.randint(H//6, H//2)
        td.ellipse([cx-rw, cy-rh, cx+rw, cy+rh],
                   fill=(random.randint(5,20), random.randint(8,30), random.randint(25,60)))
    tex = tex.filter(ImageFilter.GaussianBlur(140))
    bg = Image.blend(bg, tex, 0.6)

    # 边缘鎏金渐变（四边向内淡出）
    edge = Image.new('RGB', (W, H), (0, 0, 0))
    ed = ImageDraw.Draw(edge)
    M = 80
    for i in range(M):
        t = (M-i) / M
        col = (int(180*t+50*(1-t)), int(140*t+35*(1-t)), int(15*t+3*(1-t)))
        w = max(1, 3 - i//30)
        ed.line([(0,i),(W,i)], fill=col, width=w)
        ed.line([(0,H-1-i),(W,H-1-i)], fill=col, width=w)
        ed.line([(i,0),(i,H)], fill=col, width=w)
        ed.line([(W-1-i,0),(W-1-i,H)], fill=col, width=w)
    edge = edge.filter(ImageFilter.GaussianBlur(5))
    bg = Image.blend(bg, edge, 0.9)

    # 四角L型金色装饰
    corner = Image.new('RGB', (W, H), (0, 0, 0))
    cd = ImageDraw.Draw(corner)
    CL = 140
    for i in range(CL):
        t = i / CL
        a = int(190 * (1 - t**0.7))
        col = (min(255,185+a//4), min(255,145+a//5), 0)
        w = max(1, 2 - i//70)
        # 左上
        cd.line([(0,i),(i,0)], fill=col, width=w)
        # 右上
        cd.line([(W-1-i,0),(W-1,i)], fill=col, width=w)
        # 左下
        cd.line([(0,H-1-i),(i,H-1)], fill=col, width=w)
        # 右下
        cd.line([(W-1-i,H-1),(W-1,H-1-i)], fill=col, width=w)
    corner = corner.filter(ImageFilter.GaussianBlur(3))
    bg = Image.blend(bg, corner, 1.0)

    out = "/Users/w/.openclaw/workspace/bg3_内容页.png"
    bg.save(out, optimize=True)
    sz = os.path.getsize(out)
    print(f"✅ 背景三完成 {sz//1024//1024}MB ({os.times().elapsed-t0:.1f}s)", flush=True)
    return out


if __name__ == "__main__":
    print("=" * 48)
    print("元神AI · 三张背景图")
    print("分辨率: 3840×2160 (4K UHD)")
    print("=" * 48)
    out1 = make_bg1()
    out2 = make_bg2()
    out3 = make_bg3()
    print("\n✅ 全部完成")
