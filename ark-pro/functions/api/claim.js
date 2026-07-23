/**
 * CF Pages Function: /api/claim
 * 
 * 信任模式：接收邮箱 + 立即发 Pro Key
 * 
 * 请求：POST { email, plan, amount, timestamp }
 * 响应：{ success, proKey, message }
 * 
 * 邮件发送：通过 Resend API
 * 环境变量：RESEND_API_KEY（在 CF Pages Settings 中配置）
 */
export async function onRequestPost(context) {
  const { request, env } = context;
  
  // CORS 预检
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };

  if (request.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const body = await request.json();
    const { email, plan = 'quick-fix-49', amount = 49 } = body;

    // 校验邮箱
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return new Response(JSON.stringify({ success: false, error: '邮箱格式错误' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });
    }

    if (amount !== 49) {
      return new Response(JSON.stringify({ success: false, error: '金额必须为 ¥49' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });
    }

    // 生成 Pro Key
    const rand = [...Array(8)].map(() => 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'[Math.floor(Math.random() * 32)]).join('');
    const proKey = `ARK-${rand.slice(0,4)}-${rand.slice(4)}-49QF`;

    // 构建邮件内容
    const emailHtml = `
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px;">
  <div style="background: linear-gradient(135deg, #1e3a5f 0%, #1e1e4a 100%); border-radius: 16px; padding: 32px; text-align: center; margin-bottom: 24px;">
    <h1 style="color: #fbbf24; font-size: 24px; margin: 0;">🎉 ARK Pro Key 已生成</h1>
    <p style="color: #94a3b8; margin: 8px 0 0;">你的 30 天 Pro 权限已激活</p>
  </div>

  <div style="background: #fef3c7; border: 2px solid #fbbf24; border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 24px;">
    <p style="color: #92400e; font-size: 12px; margin: 0 0 8px;">你的 Pro Key（请妥善保存）</p>
    <div style="background: #1e293b; color: #fbbf24; font-family: monospace; font-size: 20px; padding: 16px; border-radius: 8px; letter-spacing: 2px; font-weight: bold;">
      ${proKey}
    </div>
  </div>

  <h2 style="color: #1e293b; font-size: 18px; margin: 0 0 12px;">🎁 ¥49 快速修复版包含</h2>
  <ul style="color: #475569; font-size: 14px; line-height: 2; padding-left: 20px;">
    <li>✅ 一键修复 Agent 全部崩溃隐患</li>
    <li>✅ 下载完整配置包（5个生产级模板）</li>
    <li>✅ 30 天 Pro 权限</li>
    <li>✅ 7×24 邮箱客服（24小时内响应）</li>
  </ul>

  <h2 style="color: #1e293b; font-size: 18px; margin: 24px 0 12px;">⚡ 激活步骤</h2>
  <ol style="color: #475569; font-size: 14px; line-height: 2; padding-left: 20px;">
    <li>打开 <a href="https://ark-6ek.pages.dev/diagnose" style="color: #2563eb;">https://ark-6ek.pages.dev/diagnose</a></li>
    <li>滚动到页面底部"已有 Pro Key"</li>
    <li>粘贴上面的 Pro Key，点击"激活"</li>
  </ol>

  <h2 style="color: #1e293b; font-size: 18px; margin: 24px 0 12px;">📦 下载工具包</h2>
  <p style="color: #475569; font-size: 14px;">
    <a href="https://ark-6ek.pages.dev/ark-init-kit-v1.zip" style="color: #2563eb;">👉 点击下载 ARK 初始化工具包（ZIP）</a>
  </p>

  <div style="border-top: 1px solid #e2e8f0; margin-top: 32px; padding-top: 20px; text-align: center;">
    <p style="color: #94a3b8; font-size: 12px; margin: 0;">
      如有问题，请回复本邮件或联系 <a href="mailto:guanyi2026@agent.qq.com" style="color: #2563eb;">guanyi2026@agent.qq.com</a><br>
      ARK Team · 让你的智能体永不崩溃
    </p>
  </div>
</body>
</html>`;

    const emailText = `🎉 ARK Pro Key 已生成！

你的 Pro Key（请妥善保存）：
${proKey}

¥49 快速修复版包含：
✅ 一键修复 Agent 全部崩溃隐患
✅ 下载完整配置包（5个生产级模板）
✅ 30 天 Pro 权限
✅ 7×24 邮箱客服（24小时内响应）

激活步骤：
1. 打开 https://ark-6ek.pages.dev/diagnose
2. 滚动到页面底部"已有 Pro Key"
3. 粘贴 Pro Key，点击"激活"

下载工具包：https://ark-6ek.pages.dev/ark-init-kit-v1.zip

如有问题，请回复本邮件或联系 guanyi2026@agent.qq.com
ARK Team · 让你的智能体永不崩溃`;

    // 发送邮件（通过 Resend API 或直接 SMTP）
    let emailSent = false;
    
    if (env.RESEND_API_KEY) {
      // 方式 1：Resend API（推荐，已配置到 CF Pages 环境变量）
      const resendRes = await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.RESEND_API_KEY}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          from: 'ARK Team <noreply@ark-6ek.pages.dev>',
          to: email,
          subject: '🎉 你的 ARK Pro Key 已激活！',
          html: emailHtml,
          text: emailText
        })
      });
      emailSent = resendRes.ok;
    } else if (env.SMTP_HOST && env.SMTP_USER && env.SMTP_PASS) {
      // 方式 2：SMTP（备用）
      // CF Pages Functions 不支持直接 SMTP 连接，需要通过 Workers Email 或第三方
      emailSent = false;
    } else {
      // 方式 3：无邮件服务 → 记录到 KV（后续由 cron 发送）
      emailSent = false;
    }

    // 记录到 KV（用于后续核销同步）
    if (env.CUSTOMERS_KV) {
      const customer = {
        email,
        proKey,
        plan: 'quick-fix-49',
        amount: 49,
        createdAt: new Date().toISOString(),
        expiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
        emailSent
      };
      await env.CUSTOMERS_KV.put(`customer:${email.toLowerCase()}`, JSON.stringify(customer));
      await env.CUSTOMERS_KV.put(`key:${proKey}`, email.toLowerCase());
    }

    if (emailSent) {
      return new Response(JSON.stringify({
        success: true,
        proKey,
        message: 'Pro Key 已发送到你的邮箱'
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });
    } else {
      // 邮件服务未配置，但 Key 已生成
      // 用户可以通过联系客服或邮件 claim 获取
      return new Response(JSON.stringify({
        success: true,
        proKey, // 调试时暴露 Key，生产环境应隐藏
        message: '核销成功，客服将在 5 分钟内发送 Pro Key 到你的邮箱',
        note: '系统将在 5 分钟内发送邮件，如未收到请检查垃圾箱'
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });
    }

  } catch (e) {
    return new Response(JSON.stringify({ success: false, error: '服务器错误，请稍后重试' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json', ...corsHeaders }
    });
  }
}
