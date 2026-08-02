// ARK 转化埋点 — 前端采集层
// 事件 POST → CF Pages Function /api/track → 飞书 Bitable
// 此文件不含密钥，可安全提交 Git
//
// 使用方式（每个投放页 <head> 末尾加一行即可，自动上报 page_view）：
//   <script src="/track.js" defer></script>
//
// 2026-08-02 巡航修复：此文件此前为死代码（零页面引用），导致 index /
// selfcheck / proof-of-state-trap / reports 四页零埋点，漏斗只看得见
// diagnose 一页。同时补上 `page` 维度——否则所有 page_view 汇成一个
// 无法归因的总数，看得见「有人来」却看不见「来看什么」。

const ARK_TRACK = (() => {
  const ENDPOINT = '/api/track';

  function anonId() {
    try {
      let id = localStorage.getItem('ark_anon_id');
      if (!id) {
        id = 'a_' + Math.random().toString(36).slice(2) + Date.now().toString(36);
        localStorage.setItem('ark_anon_id', id);
      }
      return id;
    } catch (e) {
      // 隐私模式 / localStorage 被禁：降级为会话内匿名 id，不阻断上报
      return 'a_' + Math.random().toString(36).slice(2) + Date.now().toString(36);
    }
  }

  function channel() {
    const r = document.referrer || '';
    if (r.includes('github.com') || r.includes('github.io')) return 'github';
    if (r.includes('news.ycombinator') || r.includes('hn.algolia')) return 'hackernews';
    if (r.includes('twitter.com') || r.includes('x.com')) return 'x';
    if (r.includes('producthunt')) return 'producthunt';
    if (r.includes('reddit.com')) return 'reddit';
    if (r.includes('dev.to')) return 'devto';
    if (r === '') return 'direct';
    return 'referral';
  }

  // 页面标识：/reports/ark-report-39167-20260801 → reports/ark-report-39167-20260801
  function page() {
    try {
      let p = (location.pathname || '/').replace(/\.html$/, '').replace(/^\/+/, '');
      if (p === '' || p === 'index') return 'home';
      if (p.endsWith('/')) p += 'index';
      return p.slice(0, 80);
    } catch (e) { return 'unknown'; }
  }

  async function send(type, extra = {}) {
    try {
      await fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, channel: channel(), anon_id: anonId(), page: page(), ...extra }),
        keepalive: true
      });
    } catch (e) { /* 静默失败：埋点永不阻断页面 */ }
  }

  const api = {
    send,
    page,
    view:          () => send('page_view'),
    diagnose:      () => send('diagnose_start'),
    payModal:      (p) => send('pay_modal_open', { product: p }),
    payIntent:     (p) => send('pay_intent', { product: p }),
    subscribeIntent:() => send('subscribe_intent'),
    paymentClaim:  (e, p) => send('payment_claim', { email: e, product: p })
  };

  // 自动 page_view：引入即生效，避免每页重复写一遍 DOMContentLoaded 样板
  // （诊断页自带内联埋点，见下方去重守卫）
  try {
    if (!window.__ARK_PV_SENT__) {
      window.__ARK_PV_SENT__ = true;
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', api.view);
      } else {
        api.view();
      }
    }
  } catch (e) { /* 忽略 */ }

  return api;
})();
