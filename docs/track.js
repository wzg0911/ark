// ARK 转化埋点 — 前端采集层
// 事件 POST → CF Pages Function /api/track → 飞书 Bitable
// 此文件不含密钥，可安全提交 Git

const ARK_TRACK = (() => {
  const ENDPOINT = '/api/track';

  function anonId() {
    let id = localStorage.getItem('ark_anon_id');
    if (!id) {
      id = 'a_' + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem('ark_anon_id', id);
    }
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
    try {
      await fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, channel: channel(), anon_id: anonId(), ...extra })
      });
    } catch (e) { /* 静默失败 */ }
  }

  // 公开API（供诊断页调用）
  return {
    view:          () => send('page_view'),
    diagnose:      () => send('diagnose_start'),
    payModal:      (p) => send('pay_modal_open', { product: p }),
    payIntent:     (p) => send('pay_intent', { product: p }),
    subscribeIntent:() => send('subscribe_intent'),
    paymentClaim:  (e, p) => send('payment_claim', { email: e, product: p })
  };
})();
