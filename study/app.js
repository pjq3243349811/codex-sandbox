'use strict';
const KEY = 'daily-study-progress-v1';
const $ = id => document.getElementById(id);
let modules = [], selected = '', completed = {}, storageAvailable = true, previousQuestion = '';
function loadProgress() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || '{}');
    if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
      completed = Object.fromEntries(Object.entries(raw).filter(([id, value]) => allLessons().some(l => l.id === id) && typeof value === 'string'));
    }
  } catch { completed = {}; $('notice').textContent = '无法读取本机打卡记录，当前从空进度开始。'; }
}
const allLessons = () => modules.flatMap(m => m.lessons);
const count = m => m.lessons.filter(l => completed[l.id]).length;
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function renderProgress() {
  const done = allLessons().filter(l => completed[l.id]).length;
  $('overall').value = done;
  $('overall-text').textContent = `已完成 ${done} / 60 天练习`;
  $('percent').textContent = `${Math.round(done / 60 * 100)}%`;
  $('modules').replaceChildren(...modules.map((m, i) => {
    const b = node('button', undefined, `module${selected === m.id ? ' active' : ''}`);
    b.setAttribute('aria-pressed', String(selected === m.id));
    b.append(node('span', m.icon, 'module-icon'));
    const label = node('span');
    label.append(node('strong', m.name), node('small', `${String(i + 1).padStart(2, '0')} · ${m.lessons.length} 天 · 已完成 ${count(m)}`));
    const progress = node('progress'); progress.max = m.lessons.length; progress.value = count(m); progress.setAttribute('aria-label', `${m.name}进度`);
    label.append(progress); b.append(label);
    b.onclick = () => { selected = m.id; $('filter').value = 'all'; render(); };
    return b;
  }));
  $('continue').disabled = false;
  $('continue').textContent = done === 60 ? '全部完成，去复习 ↗' : '继续下一次练习 ↗';
  $('review').disabled = false;
}
function lessonCard(l) {
  const card = node('details', undefined, `lesson${completed[l.id] ? ' done' : ''}`); card.id = l.id;
  const summary = node('summary');
  const heading = node('div', undefined, 'lesson-heading');
  heading.append(node('h3', l.title), node('p', `${l.minutes} 分钟 · ${completed[l.id] ? '已打卡' : '未完成'}${l.detailed ? '' : ' · 课程提纲'}`));
  summary.append(node('span', completed[l.id] ? '✓' : `${l.day} 天`, 'day'), heading, node('span', '⌄', 'chevron'));
  const body = node('div', undefined, 'lesson-body');
  body.append(node('h4', '练习步骤'));
  if (l.detailed) {
    const ol = node('ol'); l.steps.forEach(s => ol.append(node('li', s))); body.append(ol);
  } else {
    body.append(node('p', '详细步骤待补充。今天先用 20–30 分钟围绕下方成品目标自主练习，完成后对照验收再打卡。', 'placeholder'));
  }
  const product = node('div', undefined, 'product'); product.append(node('h4', '今日成品'), node('p', l.product)); body.append(product, node('h4', '验收清单'));
  const checklist = node('ul', undefined, 'checklist'); l.checklist.forEach(c => checklist.append(node('li', c))); body.append(checklist);
  const actions = node('div', undefined, 'lesson-actions');
  actions.append(node('small', completed[l.id] ? `打卡于 ${new Date(completed[l.id]).toLocaleDateString('zh-CN')}` : '先完成成品并逐项验收，再打卡。'));
  const button = node('button', completed[l.id] ? '撤销打卡' : '完成练习，打卡 ✓');
  button.onclick = () => {
    if (completed[l.id]) delete completed[l.id]; else completed[l.id] = new Date().toISOString();
    try { localStorage.setItem(KEY, JSON.stringify(completed)); storageAvailable = true; }
    catch { storageAvailable = false; }
    $('notice').textContent = storageAvailable ? '' : '浏览器无法保存记录：本次进度仅在当前页面有效，请允许网站存储。';
    const replacement = lessonCard(l); replacement.open = true; card.replaceWith(replacement);
    renderProgress(); updateModuleCount();
    if ($('filter').value !== 'all') renderLessons();
  };
  actions.append(button); body.append(actions); card.append(summary, body); return card;
}
function updateModuleCount() { const m = modules.find(m => m.id === selected); $('module-count').textContent = `${count(m)} / ${m.lessons.length} 已完成`; }
function renderLessons() {
  const m = modules.find(m => m.id === selected);
  const filtered = m.lessons.filter(l => $('filter').value === 'all' || ($('filter').value === 'done' ? completed[l.id] : !completed[l.id]));
  $('lessons').replaceChildren(...(filtered.length ? filtered.map(lessonCard) : [node('p', '当前没有符合条件的课程。换个筛选条件看看吧。', 'empty')]));
}
function render() {
  const m = modules.find(m => m.id === selected);
  $('module-title').textContent = m.name;
  $('module-range').textContent = `DAY ${String(m.lessons[0].day).padStart(2, '0')} — ${m.lessons.at(-1).day} / 学习路线`;
  $('module-description').textContent = m.description;
  renderProgress(); updateModuleCount(); renderLessons();
}
function drawQuestion() {
  let pool = allLessons().filter(l => completed[l.id]);
  $('answer').open = false;
  if (!pool.length) {
    $('quiz-source').textContent = '题库还在等你';
    $('quiz-question').textContent = '先完成一次练习并打卡，再来随机复习吧。';
    $('answer').hidden = true; $('next-question').disabled = true; return;
  }
  $('answer').hidden = false; $('next-question').disabled = false;
  if (pool.length > 1) pool = pool.filter(l => l.id !== previousQuestion);
  const l = pool[Math.floor(Math.random() * pool.length)]; previousQuestion = l.id;
  $('quiz-source').textContent = `第 ${l.day} 天 · ${l.title}`;
  $('quiz-question').textContent = l.question;
  $('quiz-answer').replaceChildren(...l.checklist.map(c => node('li', c)));
}
$('review').onclick = () => { drawQuestion(); $('quiz').showModal(); };
$('next-question').onclick = drawQuestion;
$('close-quiz').onclick = () => $('quiz').close();
$('filter').onchange = renderLessons;
$('continue').onclick = () => {
  const next = allLessons().find(l => !completed[l.id]);
  if (!next) { $('review').click(); return; }
  selected = modules.find(m => m.lessons.includes(next)).id; $('filter').value = 'all'; render();
  const card = $(next.id); card.open = true; card.scrollIntoView({behavior:'auto', block:'start'}); card.querySelector('summary').focus({preventScroll:true});
};
window.addEventListener('storage', e => { if (e.key === KEY || e.key === null) { loadProgress(); render(); if ($('quiz').open) drawQuestion(); } });
async function init() {
  try {
    const response = await fetch('./exercises.json');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json(); modules = data.modules; selected = modules[0].id;
    loadProgress(); render();
  } catch {
    $('overall-text').textContent = '课程暂时未能加载';
    $('notice').textContent = '请通过本地 HTTP 服务或 GitHub Pages 打开，检查 exercises.json 是否存在，然后刷新重试。';
  }
}
init();
