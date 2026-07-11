export async function onRequest({ env }) {
  const { FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_BITABLE, FEISHU_TABLE } = env;
  return new Response(JSON.stringify({
    has_app_id: !!FEISHU_APP_ID,
    has_app_secret: !!FEISHU_APP_SECRET,
    has_bitable: !!FEISHU_BITABLE,
    has_table: !!FEISHU_TABLE,
    app_id_prefix: FEISHU_APP_ID ? FEISHU_APP_ID.substring(0, 8) + '...' : null,
    secret_prefix: FEISHU_APP_SECRET ? FEISHU_APP_SECRET.substring(0, 8) + '...' : null,
    bitable: FEISHU_BITABLE,
    table: FEISHU_TABLE
  }), { headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' } });
}
