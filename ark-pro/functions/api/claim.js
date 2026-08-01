/**
 * CF Pages Function: /api/claim
 *
 * 双档价（胜而后战·A项修复）：
 *   1. 接收邮箱 + 记录「待核销」申请
 *   2. 不生成 / 不返回 Pro Key（防止未付款白嫖）
 *   3. 引导用户发送支付截图到客服邮箱
 *   4. 主人确认收款后，用 manual_activate.py 生成并交付 Pro Key
 *
 * 支持两档：¥49 极速修复（自动） / ¥199 深度诊断（含人工复核）
 *
 * 请求：POST { email, plan, amount }
 * 响应：{ success, status, plan, productType, message }
 */
export async function onRequestPost(context) {
  const { request, env } = context;

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
    const { email, amount = 49 } = body;

    // 校验邮箱
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return new Response(JSON.stringify({ success: false, error: '邮箱格式错误' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });
    }

    // 双档价校验：基础档 ¥49 / 深度档 ¥199
    if (amount !== 49 && amount !== 199) {
      return new Response(JSON.stringify({ success: false, error: '金额必须为 ¥49 或 ¥199' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });
    }

    const planName = amount === 199 ? 'deep-diagnosis-199' : 'quick-fix-49';
    const productType = amount === 199 ? '深度诊断（含人工复核）' : '极速修复（自动）';

    const pending = {
      email: email.toLowerCase(),
      plan: planName,
      productType,
      amount,
      status: 'pending_payment',
      createdAt: new Date().toISOString(),
      note: '等待用户发送支付截图 + 主人确认收款'
    };

    if (env.CUSTOMERS_KV) {
      const existing = await env.CUSTOMERS_KV.get(`customer:${email.toLowerCase()}`);
      if (existing) {
        const c = JSON.parse(existing);
        if (c.status === 'delivered' && c.proKey) {
          return new Response(JSON.stringify({
            success: true,
            status: 'already_delivered',
            plan: c.plan,
            productType: c.productType,
            message: '该邮箱已发货，请查收邮件或联系客服获取 Pro Key'
          }), { status: 200, headers: { 'Content-Type': 'application/json', ...corsHeaders } });
        }
      }
      await env.CUSTOMERS_KV.put(`customer:${email.toLowerCase()}`, JSON.stringify(pending));
    }

    return new Response(JSON.stringify({
      success: true,
      status: 'pending_payment',
      plan: planName,
      productType,
      message: '申请已收到！请截图微信/支付宝支付记录，发送到 guanyi2026@agent.qq.com（备注你的邮箱），确认收款后 5 分钟内发货。'
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json', ...corsHeaders }
    });

  } catch (e) {
    return new Response(JSON.stringify({ success: false, error: '服务器错误，请稍后重试' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json', ...corsHeaders }
    });
  }
}
