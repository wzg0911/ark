/**
 * CF Pages Function: /api/stats
 * 聚合 CUSTOMERS_KV 中的漏斗事件，供 growth-tracker.py 读取真实增长数据。
 * 返回：{ page_views, diagnosis_starts, claim_attempts, claim_success, customers }
 */
export async function onRequestGet(context) {
  const { env } = context;
  const cors = { 'Access-Control-Allow-Origin': '*' };
  const zero = { page_views: 0, diagnosis_starts: 0, claim_attempts: 0, claim_success: 0, customers: 0 };
  if (!env.CUSTOMERS_KV) {
    return new Response(JSON.stringify({ ok: false, ...zero }), {
      status: 200, headers: { 'Content-Type': 'application/json', ...cors },
    });
  }
  try {
    const agg = { page_views: 0, diagnosis_starts: 0, claim_attempts: 0, claim_success: 0, customers: 0 };
    let cursor;
    do {
      const page = await env.CUSTOMERS_KV.list({ prefix: 'event:', cursor });
      for (const k of page.keys) {
        const ev = k.name.split(':')[1] || '';
        if (ev in agg) agg[ev] += 1;
      }
      cursor = page.list_complete ? undefined : page.cursor;
    } while (cursor);
    // 客户数：以 customer: 前缀统计
    const custPage = await env.CUSTOMERS_KV.list({ prefix: 'customer:' });
    agg.customers = custPage.keys.length;
    return new Response(JSON.stringify({ ok: true, ...agg }), {
      status: 200, headers: { 'Content-Type': 'application/json', ...cors },
    });
  } catch (e) {
    return new Response(JSON.stringify({ ok: false, ...zero }), {
      status: 200, headers: { 'Content-Type': 'application/json', ...cors },
    });
  }
}
