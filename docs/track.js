// ARK 转化埋点（轻量，零第三方cookie）
// 通过飞书群机器人 webhook 上报（不暴露 app_secret）
// webhook URL 在部署前由本地脚本注入（占位符避免提交密钥）
const ARK_WEBHOOK = "__ARK_WEBHOOK_PLACEHOLDER__";

const ARK_TRACK = (() => {
  function anonId() {
    let id = localStorage.getItem('ark_anon_id');
    if (!id) { id = 'a_' + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem('ark_anon_id', id); }
    return id;
  }
  function channel() {
    const r = document.referrer || '';
    if (r.includes('github.com') || r.includes('github.io')) return 'github';
    if (r.includes('dev.to')) return 'devto';
    if (r === '') return 'direct';
    return 'other';
  }
  async function send(type, extra = {}) {
    if (!ARK_WEBHOOK || ARK_WEBHOOK.startsWith('__')) return; // 未配置则静默
    try {
      const msg = {
        "msg_type": "text",
        "content": { "text": `[ARK追踪] ${type} | 渠道:${channel()} | 匿名:${anonId()}` +
          (extra.product ? ` | 产品:${extra.product}` : '') +
          (extra.email ? ` | 邮箱:${extra.email}` : '') }
      };
      await fetch(ARK_WEBHOOK, { method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify(msg) });
    } catch (e) { /* 静默失败 */ }
  }
  return {
    view: () => send('page_view'),
    diagnose: () => send('diagnose_start'),
    payModal: (p) => send('pay_modal_open', { product: p }),
    payIntent: (p) => send('pay_intent', { product: p }),
    subscribeIntent: () => send('subscribe_intent'),
    paymentClaim: (e, p) => send('payment_claim', { email: e, product: p })
  };
})();
