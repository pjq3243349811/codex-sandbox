'use strict';
const $=id=>document.getElementById(id), KEY='douyin-topics.v1', form=$('topic-form');
const TEMPLATE=`【0–3 秒｜钩子】
配音：痛点 + 具体结果。
画面：先展示最终效果，放大关键区域。

【3–10 秒｜场景与工具】
配音：适合谁？工具入口、费用与准备材料。
画面：展示工具入口，遮挡隐私信息。

【10–45 秒｜三步录屏演示】
1. 准备：导入素材或输入问题。
2. 操作：演示关键按钮与提示词。
3. 产出：展示结果，解释如何调整。
配音：每步只讲一个动作，留出操作停顿。

【45–55 秒｜结果验证】
画面：前后对比，展示真实输出。
配音：说明效果、局限与注意事项。

【55–60 秒｜总结与引导】
配音：总结适用场景，引导收藏或评论需求。
画面：三步流程总结字幕。`;
let state={topics:[],ideas:[]}, editing=null, sourceIdea=null;
const uid=()=>crypto.randomUUID?.()||`${Date.now()}-${Math.random()}`;
const notify=text=>$('notice').textContent=text;
function validUrl(s){try{return ['http:','https:'].includes(new URL(s).protocol);}catch{return false;}}
function validate(d){
 if(!d||d.version!==1||!Array.isArray(d.topics)||!Array.isArray(d.ideas)||d.topics.length+d.ideas.length>10000)throw Error('备份结构或版本无效');
 const ids=new Set(); const checkId=t=>{if(!t||typeof t.id!=='string'||!t.id||ids.has(t.id))throw Error('记录 ID 无效或重复');ids.add(t.id);};
 const topics=d.topics.map(t=>{checkId(t);for(const [k,max] of [['title',200],['hook',3000],['outline',30000]])if(typeof t[k]!=='string'||t[k].length>max)throw Error('选题文字字段无效');if(!t.title.trim()||!['待拍','已拍','已发'].includes(t.status))throw Error('标题或状态无效');if(!Array.isArray(t.tags)||t.tags.some(x=>typeof x!=='string')||t.tags.join(',').length>1000)throw Error('标签无效');if(!Array.isArray(t.links)||t.links.some(x=>typeof x!=='string'||!validUrl(x))||t.links.join('\n').length>10000)throw Error('素材链接无效');return {id:t.id,title:t.title,hook:t.hook,outline:t.outline,links:t.links,status:t.status,tags:t.tags};});
 const ideas=d.ideas.map(i=>{checkId(i);if(typeof i.text!=='string'||!i.text.trim()||i.text.length>2000)throw Error('灵感无效');return {id:i.id,text:i.text};});return {topics,ideas};
}
try{const raw=localStorage.getItem(KEY);if(raw)state=validate(JSON.parse(raw));}catch{notify('本地数据读取失败，请检查浏览器存储设置，先保留已有备份。');}
function save(next){try{localStorage.setItem(KEY,JSON.stringify({version:1,...next}));state=next;render();notify('已保存到当前浏览器');return true;}catch{notify('保存失败：存储不可用或已满，请导出备份后重试。');return false;}}
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function btn(text,action,cls){const b=el('button',text,cls);b.type='button';b.onclick=action;return b;}
function render(){
 $('stats').replaceChildren(...['全部选题','待拍','已拍','已发'].map((s,i)=>{const n=el('div',s,'stat');n.prepend(el('strong',i?state.topics.filter(t=>t.status===s).length:state.topics.length));return n;}));
 const old=$('tag-filter').value;const tags=[...new Set(state.topics.flatMap(t=>t.tags))].sort();$('tag-filter').replaceChildren(new Option('全部标签',''),...tags.map(t=>new Option(t,t)));$('tag-filter').value=tags.includes(old)?old:'';
 const q=$('search').value.trim().toLowerCase(),s=$('status-filter').value,tag=$('tag-filter').value;
 const shown=state.topics.filter(t=>(!s||t.status===s)&&(!tag||t.tags.includes(tag))&&[t.title,t.hook,t.outline,...t.tags,...t.links].join(' ').toLowerCase().includes(q));$('count').textContent=`${shown.length} / ${state.topics.length}`;
 $('cards').replaceChildren(...shown.map(t=>{const c=el('article',undefined,'card'),badge=el('span',t.status,'badge'),top=el('div');badge.dataset.status=t.status;top.append(badge);c.append(top,el('h3',t.title),el('div',t.hook||'还没有钩子，试试用一句话展示最终效果。','hook'));const tags=el('div');t.tags.forEach(x=>tags.append(el('span',`# ${x}`,'tag')));c.append(tags);
 if(t.outline||t.links.length){const d=el('details');d.append(el('summary','查看脚本与素材'));if(t.outline)d.append(el('pre',t.outline));t.links.forEach(url=>{const a=el('a',url);a.href=url;a.target='_blank';a.rel='noopener noreferrer';d.append(a);});c.append(d);}const actions=el('div',undefined,'actions');actions.append(btn('编辑',()=>openEditor(t)),btn('删除',()=>{if(confirm(`删除选题「${t.title}」？`))save({...state,topics:state.topics.filter(x=>x.id!==t.id)});},'danger'));c.append(actions);return c;}));
 if(!shown.length){const empty=el('div',undefined,'empty');empty.append(el('strong',state.topics.length?'没有匹配的选题':'你的下一条作品，从这里开始'),el('p',state.topics.length?'调整关键词、状态或标签，再找找看。':'新建一个选题，或把灵感转成卡片。'));$('cards').append(empty);}
 $('ideas').replaceChildren(...state.ideas.map(i=>{const li=el('li');li.append(el('div',i.text),btn('转为选题',()=>openEditor(null,i)),btn('删除',()=>{if(confirm('删除这条灵感？'))save({...state,ideas:state.ideas.filter(x=>x.id!==i.id)});},'danger'));return li;}));
}
function openEditor(t=null,i=null){editing=t?.id||null;sourceIdea=i?.id||null;form.reset();$('editor-title').textContent=t?'编辑选题':'新建选题';for(const k of ['title','hook','outline','status'])form.elements[k].value=t?.[k]||(k==='status'?'待拍':k==='title'?(i?.text||'').slice(0,200):'');if(i&&i.text.length>200)form.elements.hook.value=i.text;form.elements.links.value=t?.links.join('\n')||'';form.elements.tags.value=t?.tags.join(', ')||'';form.elements.title.setCustomValidity('');$('editor').showModal();}
$('new').onclick=()=>openEditor();$('cancel').onclick=$('close').onclick=()=>$('editor').close();
$('use-template').onclick=()=>{if(!form.elements.outline.value.trim()||confirm('用模板替换当前脚本大纲？'))form.elements.outline.value=TEMPLATE;};
form.elements.title.oninput=()=>form.elements.title.setCustomValidity('');
form.onsubmit=e=>{e.preventDefault();const v=k=>form.elements[k].value.trim(),links=v('links').split(/\r?\n/).map(x=>x.trim()).filter(Boolean);if(links.some(x=>!validUrl(x))){alert('素材链接请逐行填写完整的 http:// 或 https:// 地址。');return;}if(!v('title')){form.elements.title.setCustomValidity('请填写标题');form.elements.title.reportValidity();return;}const t={id:editing||uid(),title:v('title'),hook:v('hook'),outline:v('outline'),status:v('status'),links,tags:[...new Set(v('tags').split(/[,，、]/).map(x=>x.trim()).filter(Boolean))]};if(save({topics:editing?state.topics.map(x=>x.id===editing?t:x):[t,...state.topics],ideas:state.ideas.filter(x=>x.id!==sourceIdea)}))$('editor').close();};
$('idea-form').onsubmit=e=>{e.preventDefault();const text=$('idea').value.trim();if(text&&save({...state,ideas:[{id:uid(),text},...state.ideas]}))$('idea').value='';};
for(const id of ['search','status-filter','tag-filter'])$(id).addEventListener(id==='search'?'input':'change',render);
$('export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({version:1,...state},null,2)],{type:'application/json'})),a=el('a');a.href=url;a.download=`douyin-topics-${new Date().toISOString().slice(0,10)}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notify('已导出选题与灵感备份');};
$('import').onclick=()=>$('file').click();$('file').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{if(file.size>10*1024*1024)throw Error('文件不能超过 10 MB');const d=validate(JSON.parse(await file.text())),ids=new Set([...state.topics,...state.ideas].map(x=>x.id)),topics=d.topics.filter(x=>!ids.has(x.id)),ideas=d.ideas.filter(x=>!ids.has(x.id));if(confirm(`合并导入 ${topics.length} 个选题、${ideas.length} 条灵感？相同 ID 保留当前版本。`))save({topics:[...topics,...state.topics],ideas:[...ideas,...state.ideas]});}catch(err){notify(`导入失败：${err.message}。当前数据未变更。`);}finally{e.target.value='';}};
render();
