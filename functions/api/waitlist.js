/**
 * CF Pages Function: /api/waitlist
 *
 * 自检清单预约收集（路径C·阶段一 MVP 前置动作）：
 *   接收邮箱，存入 CUSTOMERS_KV，待《Agent崩溃风险自检清单》上线后通知。
 *
 * 请求：POST { email }
 * 响应：{ success, message }
 */
export async function onRequestPost(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
  if (request.method === 'OPTIONS') return new Response(null, { headers: corsHeaders });

  try {
    const body = await request.json();
    const email = (body.email || '').toString().trim().toLowerCase();
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return new Response(JSON.stringify({ success: false, error: '邮箱格式错误' }), {
        status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });
    }
    if (env.CUSTOMERS_KV) {
      const existing = await env.CUSTOMERS_KV.get(`waitlist:${email}`);
      if (!existing) {
        await env.CUSTOMERS_KV.put(`waitlist:${email}`, JSON.stringify({
          email, joinedAt: new Date().toISOString(), source: 'diagnose_preview'
        }));
      }
    }
    return new Response(JSON.stringify({
      success: true,
      message: '已登记！《Agent崩溃风险自检清单》上线后，我会第一时间发邮件通知你。'
    }), { status: 200, headers: { 'Content-Type': 'application/json', ...corsHeaders } });
  } catch (e) {
    return new Response(JSON.stringify({ success: false, error: '服务器错误，请稍后重试' }), {
      status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders }
    });
  }
}
