/**
 * CF Pages Function: /api/waitlist
 *
 * 自检清单预约写入飞书 Bitable（胜而后战·C项修复）：
 * 前端 diagnose.html 的 waitlist 表单提交后，POST 邮箱到此端点，
 * 经飞书环境变量（FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_BITABLE / FEISHU_TABLE）
 * 写入 Bitable 表，与 /api/stats 共用同一数据源。
 *
 * 请求：POST { email }
 * 响应：{ ok, record }
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

  const { FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_BITABLE, FEISHU_TABLE } = env;
  if (!FEISHU_APP_ID || !FEISHU_APP_SECRET || !FEISHU_BITABLE || !FEISHU_TABLE) {
    return new Response(JSON.stringify({ ok: false, reason: 'env_not_configured' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json', ...cors },
    });
  }

  try {
    const body = await request.json().catch(() => ({}));
    const email = (body.email || '').toString().slice(0, 128);
    if (!email) {
      return new Response(JSON.stringify({ ok: false, reason: 'empty_email' }), {
        status: 200, headers: { 'Content-Type': 'application/json', ...cors },
      });
    }

    const tokResp = await fetch('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ app_id: FEISHU_APP_ID, app_secret: FEISHU_APP_SECRET }),
    });
    const tokData = await tokResp.json();
    const token = tokData.tenant_access_token;
    if (!token) {
      return new Response(JSON.stringify({ ok: false, reason: 'token_failed' }), {
        status: 200, headers: { 'Content-Type': 'application/json', ...cors },
      });
    }

    const res = await fetch(`https://open.feishu.cn/open-apis/bitable/v1/apps/${FEISHU_BITABLE}/tables/${FEISHU_TABLE}/records`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        fields: {
          '邮箱(文本)': email,
          '来源渠道': 'waitlist_form',
          '提交时间': new Date().toISOString(),
        },
      }),
    });

    return new Response(JSON.stringify({ ok: res.ok, record: email }), {
      status: 200, headers: { 'Content-Type': 'application/json', ...cors },
    });
  } catch (e) {
    return new Response(JSON.stringify({ ok: false, reason: String(e && e.message || e) }), {
      status: 200, headers: { 'Content-Type': 'application/json', ...cors },
    });
  }
}
