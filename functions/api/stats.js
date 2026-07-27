/**
 * CF Pages Function: /api/stats
 * 聚合真实漏斗（飞书 Bitable，前端经 /api/track 写入），供 growth-tracker.py 读取真实增长数据。
 * 复用 CF Dashboard 已配置的飞书环境变量（FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_BITABLE / FEISHU_TABLE）。
 *
 * 返回（与 growth-tracker 消费字段对齐，并扩展）：
 *   { ok, page_views, diagnosis_starts, claim_attempts, claim_success, pay_intents, customers, real_visitors, channels }
 */
export async function onRequestGet(context) {
  const { env } = context;
  const cors = { 'Access-Control-Allow-Origin': '*' };
  const zero = {
    page_views: 0, diagnosis_starts: 0, claim_attempts: 0, claim_success: 0,
    pay_intents: 0, customers: 0, real_visitors: 0, channels: {}
  };

  const { FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_BITABLE, FEISHU_TABLE } = env;
  if (!FEISHU_APP_ID || !FEISHU_APP_SECRET || !FEISHU_BITABLE || !FEISHU_TABLE) {
    return new Response(JSON.stringify({ ok: false, reason: 'env_not_configured', ...zero }), {
      status: 200, headers: { 'Content-Type': 'application/json', ...cors },
    });
  }

  try {
    // 1) 取 tenant_access_token
    const tokResp = await fetch('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ app_id: FEISHU_APP_ID, app_secret: FEISHU_APP_SECRET }),
    });
    const tokData = await tokResp.json();
    const token = tokData.tenant_access_token;
    if (!token) {
      return new Response(JSON.stringify({ ok: false, reason: 'token_failed', ...zero }), {
        status: 200, headers: { 'Content-Type': 'application/json', ...cors },
      });
    }

    // 2) 分页读取 Bitable 全部记录
    const agg = { ...zero };
    const seen = new Set();
    let pageToken;
    do {
      let url = `https://open.feishu.cn/open-apis/bitable/v1/apps/${FEISHU_BITABLE}/tables/${FEISHU_TABLE}/records?page_size=100`;
      if (pageToken) url += `&page_token=${encodeURIComponent(pageToken)}`;
      const recResp = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      const recData = await recResp.json();
      for (const row of (recData.records || [])) {
        const f = row.fields || {};
        const type = f['事件类型'] || f['type'] || '';
        const anon = String(f['匿名标识'] || f['anon_id'] || '');
        const channel = String(f['来源渠道'] || f['channel'] || 'direct');
        const isReal = anon.startsWith('a_') && !anon.startsWith('anon_test');
        if (type === 'page_view' || type === 'view') {
          agg.page_views += 1;
          if (isReal && !seen.has(anon)) { seen.add(anon); agg.real_visitors += 1; }
        } else if (type === 'diagnosis_start') {
          agg.diagnosis_starts += 1;
        } else if (type === 'claim_attempt' || type === 'claim_pending') {
          agg.claim_attempts += 1;
        } else if (type === 'claim_success') {
          agg.claim_success += 1;
        } else if (type === 'pay_intent' || type === 'pay_modal_open') {
          agg.pay_intents += 1;
        }
        if (f['邮箱(文本)'] || f['邮箱']) agg.customers += 1;
        if (channel) agg.channels[channel] = (agg.channels[channel] || 0) + 1;
      }
      pageToken = recData.has_more ? recData.page_token : undefined;
    } while (pageToken);

    return new Response(JSON.stringify({ ok: true, ...agg }), {
      status: 200, headers: { 'Content-Type': 'application/json', ...cors },
    });
  } catch (e) {
    return new Response(JSON.stringify({ ok: false, reason: 'exception', detail: String(e && e.message || e), ...zero }), {
      status: 200, headers: { 'Content-Type': 'application/json', ...cors },
    });
  }
}
