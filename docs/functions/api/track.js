// CF Pages Function: ARK 转化埋点代理
// 前端 POST /api/track → 此函数写飞书 Bitable
// 环境变量(CF Dashboard Settings → Environment variables):
//   FEISHU_APP_ID     = cli_a949e8f4f2b85cc2
//   FEISHU_APP_SECRET = s9EHvwTkgXzl...
//   FEISHU_BITABLE    = X3ZcbcJnHaCffBs2HVzcBR6Bnff
//   FEISHU_TABLE      = tbleFRx9UgGHBqy9

export async function onRequestPost({ request, env }) {
  const { FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_BITABLE, FEISHU_TABLE } = env;
  if (!FEISHU_APP_ID || !FEISHU_APP_SECRET) {
    return new Response(JSON.stringify({ ok: false, reason: 'env_not_configured' }), { status: 500 });
  }

  let body;
  try { body = await request.json(); } catch {
    return new Response(JSON.stringify({ ok: false, reason: 'invalid_json' }), { status: 400 });
  }

  const { type, channel, anon_id, product, email } = body;
  if (!type) return new Response(JSON.stringify({ ok: false, reason: 'missing_type' }), { status: 400 });

  // 取飞书 token（带 5 分钟缓存）
  const token = await getFeishuToken(FEISHU_APP_ID, FEISHU_APP_SECRET);

  const fields = {
    '事件类型': type,
    '来源渠道': channel || 'direct',
    '匿名标识': anon_id || 'unknown'
  };
  if (product) fields['产品类型'] = product;
  if (email) fields['邮箱(文本)'] = email;

  try {
    const resp = await fetch(
      `https://open.feishu.cn/open-apis/bitable/v1/apps/${FEISHU_BITABLE}/tables/${FEISHU_TABLE}/records`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ fields })
      }
    );
    const data = await resp.json();
    return new Response(JSON.stringify({ ok: data.code === 0, code: data.code }), {
      status: data.code === 0 ? 200 : 500,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
  } catch (e) {
    return new Response(JSON.stringify({ ok: false, reason: 'fetch_error', detail: e.message }), { status: 500 });
  }
}

export async function onRequestOptions() {
  return new Response(null, {
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type'
    }
  });
}

// 内存级 token 缓存（CF Function 实例复用期有效）
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
