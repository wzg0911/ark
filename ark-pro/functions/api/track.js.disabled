/**
 * CF Pages Function: /api/track
 *
 * 前端 diagnose.html（线上版 arkEvent 调用的真实落点）POST 漏斗事件到此端点。
 * 写入 CUSTOMERS_KV，供 /api/stats 与 growth-tracker.py 聚合读取。
 * 与 event.js 同源，但保留 /api/track 命名以兼容已部署前端。
 *
 * 请求：POST { event, meta }
 * 响应：{ ok }
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
    return new Response(JSON.stringify({ ok: true, event: name }), {
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
