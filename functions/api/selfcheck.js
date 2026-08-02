/**
 * CF Pages Function: /api/selfcheck
 *
 * 自检清单完成埋点（胜而后战·B项修复）：
 * 前端 selfcheck.html 在用户走完三大故障模式（幂等边界 / 状态生命周期 / 重试风暴）
 * 并提交邮箱后，POST 一个 selfcheck_complete 事件到此处，后端记入 CUSTOMERS_KV，
 * 供 /api/stats 与 growth-tracker.py 聚合读取。
 *
 * 请求：POST { email }
 * 响应：{ ok, event }
 */
export async function onRequestPost(context) {
  const { request, env } = context;
  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };

  if (request.method === 'OPTIONS') {
    return new Response(null, { headers: cors });
  }

  try {
    const body = await request.json().catch(() => ({}));
    const email = (body.email || '').toString().slice(0, 128);
    const rec = {
      event: 'selfcheck_complete',
      email,
      ts: new Date().toISOString(),
      ua: request.headers.get('user-agent') || '',
      ref: request.headers.get('referer') || '',
    };
    if (env.CUSTOMERS_KV) {
      const key = `event:${Date.now()}:${Math.random().toString(36).slice(2, 8)}`;
      await env.CUSTOMERS_KV.put(key, JSON.stringify(rec));
    }
    return new Response(JSON.stringify({ ok: true, event: 'selfcheck_complete' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json', ...cors },
    });
  } catch (e) {
    return new Response(JSON.stringify({ ok: false }), {
      status: 200,
      headers: { 'Content-Type': 'application/json', ...cors },
    });
  }
}
