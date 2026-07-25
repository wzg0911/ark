/**
 * CF Pages Function: /api/verify
 * 
 * 验证 Pro Key 有效性
 * 
 * 请求：POST { key }
 * 响应：{ valid, daysLeft, plan, error }
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
    const { key } = body;

    if (!key || typeof key !== 'string') {
      return new Response(JSON.stringify({ valid: false, error: 'Key 不能为空' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });
    }

    const keyUpper = key.trim().toUpperCase();

    // 格式校验
    const keyMatch = keyUpper.match(/^ARK-([A-Z0-9]{4})-([A-Z0-9]{4})-49QF$/);
    if (!keyMatch) {
      return new Response(JSON.stringify({ valid: false, error: 'Key 格式错误' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });
    }

    // 尝试从 KV 验证
    if (env.CUSTOMERS_KV) {
      const email = await env.CUSTOMERS_KV.get(`key:${keyUpper}`);
      if (email) {
        const customerStr = await env.CUSTOMERS_KV.get(`customer:${email}`);
        if (customerStr) {
          const customer = JSON.parse(customerStr);
          const created = new Date(customer.createdAt);
          const expires = new Date(created.getTime() + 30 * 24 * 60 * 60 * 1000);
          const now = new Date();
          const daysLeft = Math.max(0, Math.ceil((expires - now) / (24 * 60 * 60 * 1000)));
          return new Response(JSON.stringify({
            valid: daysLeft > 0,
            daysLeft,
            plan: customer.plan,
            email,
            expiresAt: expires.toISOString()
          }), {
            status: 200,
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }
      }
    }

    // 无 KV 或 KV 中不存在 → 宽松验证（信任模式）
    // 格式正确即认为有效（30天有效期）
    return new Response(JSON.stringify({
      valid: true,
      daysLeft: 30,
      plan: 'quick-fix-49',
      note: '信任模式激活'
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json', ...corsHeaders }
    });

  } catch (e) {
    return new Response(JSON.stringify({ valid: false, error: '服务器错误' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json', ...corsHeaders }
    });
  }
}
