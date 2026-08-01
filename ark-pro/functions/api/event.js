/**
 * CF Pages Function: /api/event
 * 轻量漏斗事件埋点（页面浏览 / 诊断开始 / claim尝试 / claim成功）
 * 写入 CUSTOMERS_KV，供 /api/stats 与 growth-tracker.py 聚合读取。
 */
export async function onRequestPost(context) {
  const { request, env } = context;
  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
  try {
    const body = await request.json().catch(() => ({}));
    const name = (body.event || 'unknown').toString().slice(0, 64);
    const rec = {
      event: name,
      meta: body.meta || {},
      ts: new Date().toISOString(),
      ua: request.headers.get('user-agent') || '',
      ref: request.headers.get('referer') || '',
    };
    if (env.CUSTOMERS_KV) {
      const key = `event:${Date.now()}:${Math.random().toString(36).slice(2, 8)}`;
      await env.CUSTOMERS_KV.put(key, JSON.stringify(rec));
    }
    return new Response(JSON.stringify({ ok: true }), {
      status: 200, headers: { 'Content-Type': 'application/json', ...cors },
    });
  } catch (e) {
    return new Response(JSON.stringify({ ok: false }), {
      status: 200, headers: { 'Content-Type': 'application/json', ...cors },
    });
  }
}

export async function onRequestOptions() {
  return new Response(null, {
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    },
  });
}
