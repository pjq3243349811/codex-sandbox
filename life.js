/* 与天气脚本隔离；外部文本使用 textContent，链接只接受 HTTP(S)。 */
(() => {
  const channels = ['weather', 'deals', 'jobs'];
  const loaded = new Set();
  const pending = new Set();
  const get = id => document.getElementById(id);
  const time = value => value && Number.isFinite(Date.parse(value))
    ? new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) : '尚未成功';
  function node(tag, value, className) {
    const el = document.createElement(tag);
    el.textContent = value;
    if (className) el.className = className;
    return el;
  }
  function link(label, value) {
    try {
      const url = new URL(value);
      if (!['https:', 'http:'].includes(url.protocol)) return node('span', '来源链接不可用');
      const a = node('a', label, 'card-link');
      a.href = url.href; a.target = '_blank'; a.rel = 'noopener noreferrer';
      return a;
    } catch { return node('span', '来源链接不可用'); }
  }
  function card(item, kind, historical) {
    const el = document.createElement('article');
    if (historical || item.historical) el.append(node('p', '历史数据 · 本次未核验', 'warning'));
    if (kind === 'deals') {
      el.append(node('h3', `大连 → ${item.destination}`));
      el.append(node('p', `¥${item.price} 起`, 'price'));
      el.append(node('p', `日期范围：${item.date_start ? `${item.date_start} ～ ${item.date_end || item.date_start}` : (item.date_note || '来源未公布，请到官网确认')}`));
      el.append(node('p', item.price_note || '价格以购票页为准', 'muted'));
      el.append(link('进入官网购票 ↗', item.booking_url));
    } else {
      el.append(node('h3', item.position), node('p', `${item.category} · ${item.unit}`));
      if (item.unrestricted_major === true) el.append(node('span', '不限专业', 'badge'));
      el.append(node('p', `学历要求：${item.education}`), node('p', `专业要求：${item.major}`));
      el.append(node('p', `报名截止：${item.deadline || '原文未明确提取，请查看公告'}`, 'warning'));
      el.append(link('查看官方公告 ↗', item.source_url));
      if (item.attachment_url) el.append(document.createElement('br'), link('查看岗位表 ↗', item.attachment_url));
    }
    return el;
  }
  async function load(kind) {
    if (pending.has(kind)) return;
    pending.add(kind); get(`refresh-${kind}`).disabled = true;
    const status = get(`${kind}-status`), cards = get(`${kind}-cards`);
    try {
      const response = await fetch(`./${kind}.json?t=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw Error('HTTP');
      const data = await response.json();
      if (!Array.isArray(data.items) || !['ok', 'partial', 'error'].includes(data.status)) throw Error('格式');
      get(`${kind}-sources`).replaceChildren(...(Array.isArray(data.sources) ? data.sources : []).flatMap(url => [link('官方数据源 ↗', url), document.createTextNode('　')]));
      const age = Date.now() - Date.parse(data.updated_at);
      const stale = !Number.isFinite(age) || age > (kind === 'deals' ? 48 : 192) * 3600000;
      const historical = data.status === 'error' || stale;
      get(`${kind}-meta`).textContent = `最后完整更新：${time(data.updated_at)} · 最近检查：${time(data.checked_at)} · 北京时间`;
      status.textContent = `${data.message || ''}${historical ? ' ⚠ 数据未成功更新或已过旧，以下为历史信息，请到来源核验。' : ''}`;
      cards.replaceChildren(...data.items.map(item => card(item, kind, historical)));
      if (!data.items.length) cards.append(node('p', data.status === 'ok' ? '本次未发现符合条件的信息。' : '暂无可核验数据，请稍后刷新或检查后台更新。', 'muted'));
      loaded.add(kind);
    } catch {
      status.textContent = '⚠ 数据文件读取失败或格式异常，请通过 HTTP 服务打开并检查后台更新。';
      if (cards.children.length) {
        status.textContent += ' 当前保留上次页面结果，属于历史信息。';
        for (const article of cards.querySelectorAll('article')) article.prepend(node('p', '历史数据 · 本次未核验', 'warning'));
      }
    } finally { pending.delete(kind); get(`refresh-${kind}`).disabled = false; }
  }
  function switchChannel() {
    const kind = channels.includes(location.hash.slice(1)) ? location.hash.slice(1) : 'weather';
    for (const channel of channels) {
      get(`channel-${channel}`).hidden = channel !== kind;
      const nav = document.querySelector(`[data-channel="${channel}"]`);
      if (channel === kind) nav.setAttribute('aria-current', 'page'); else nav.removeAttribute('aria-current');
    }
    if (kind !== 'weather' && !loaded.has(kind)) load(kind);
  }
  for (const kind of ['deals', 'jobs']) get(`refresh-${kind}`).addEventListener('click', () => load(kind));
  window.addEventListener('hashchange', switchChannel);
  switchChannel();
})();
