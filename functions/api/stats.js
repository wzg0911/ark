// CF Pages Function: ARK 统计看板数据
// GET /api/stats → 返回诊断次数、MRR等实时数据
// 环境变量: FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_BITABLE, FEISHU_TABLE

export async function onRequestGet({ env }) {
  const { FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_BITABLE, FEISHU_TABLE } = env;
  if (!FEISHU_APP_ID || !FEISHU_APP_SECRET) {
    return new Response(JSON.stringify({ configured: false }), {
      status: 200, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
  }

  try {
    const token = await getFeishuToken(FEISHU_APP_ID, FEISHU_APP_SECRET);

    // 统计各事件类型数量（pageSize=1仅取总数）
    const [pageViews, diagnoses, payIntents] = await Promise.all([
      countEvents(token, FEISHU_BITABLE, FEISHU_TABLE, 'page_view'),
      countEvents(token, FEISHU_BITABLE, FEISHU_TABLE, 'diagnose_start'),
      countEvents(token, FEISHU_BITABLE, FEISHU_TABLE, 'pay_intent')
    ]);

    return new Response(JSON.stringify({
      configured: true,
      diagnoses: diagnoses,
      page_views: pageViews,
      pay_intents: payIntents,
      mrr: `¥${payIntents * 65}` // 估算：每个 pay_intent = ¥65/月订阅
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=30' }
    });
  } catch (e) {
    return new Response(JSON.stringify({ configured: true, error: e.message }), {
      status: 500, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
  }
}

async function countEvents(token, bitable, table, eventType) {
  const resp = await fetch(
    `https://open.feishu.cn/open-apis/bitable/v1/apps/${bitable}/tables/${table}/records?page_size=1&filter=CurrentValue.%5B%E4%BA%8B%E4%BB%B6%E7%B1%BB%E5%9E%8B%5D%3D%22${encodeURIComponent(eventType)}%22`,
    { headers: { 'Authorization': `Bearer ${token}` } }
  );
  const d = await resp.json();
  return d.data?.total || 0;
}

let _tokenCache = { t: '', exp: 0 };
async function getFeishuToken(appId, appSecret) {
  const now = Date.now();
  if (_tokenCache.t && now < _tokenCache.exp) return _tokenCache.t;
  const resp = await fetch('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ app_id: appId, app_secret: appSecret })
  });
  const d = await resp.json();
  _tokenCache = { t: d.tenant_access_token, exp: now + (d.expire - 120) * 1000 };
  return _tokenCache.t;
}
