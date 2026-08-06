/**
 * DEPRECATED — 此文件已废弃（2026-08-06）。
 *
 * 历史：与根目录 functions/api/track.js 同名同路径、契约互不兼容
 * （{event,meta} vs {type,channel,anon_id,page}）。线上生效的始终是
 * 根目录版（写飞书 Bitable，响应 {ok,code}），本文件从未被部署。
 *
 * 风险：Cloudflare Pages 部署根目录 functions/ 时不会包含 ark-pro/ 子目录，
 * 本文件为死代码；若未来有人将 ark-pro/ 作为 Pages 项目根目录部署，
 * 此文件会以 {event,meta} 契约覆盖线上埋点，导致 stats.js 与飞书管道全部失效。
 *
 * 处理：保留 .disabled 备份（track.js.disabled），本文件内容替换为显式
 * 失败响应——任何请求都会得到 410 Gone，绝不可能再被误当可用端点。
 */
export async function onRequestPost() {
  return new Response(JSON.stringify({ ok: false, reason: 'deprecated_use_root_track' }), {
    status: 410,
    headers: { 'Content-Type': 'application/json' },
  });
}
