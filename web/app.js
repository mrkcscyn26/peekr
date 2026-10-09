/* C1 Interface. Implements F1-F7 in the browser (T-08, T-11).
   Covers FR-1, FR-2, FR-5, FR-9 to FR-16, FR-18, FR-20, FR-25.

   Plain ES module, no build step. All data comes from the same-origin /api endpoints in Section 8.8
   (FR-23); times are shown in the browser's local time zone.
   Polling (no push in the MVP): index status every 1 s, health every 5 s, library (folders, files,
   skipped files) and the Activity feed every 5 s, file metadata + history every 3 s while the detail
   panel is open (F5 step 8). Polling pauses while the tab is hidden.

   Assumptions (flagged):
   - Match strength is read from the RRF score and assumes search.rrf_k = 60: Strong >= 0.025 (ranked
     high in both the vector and the keyword list), Good >= 0.014 (top of one list), else Possible.
   - Searches ask for 10 results (F3 default). While a category or folder scope is active, 100 are
     fetched and filtered in the browser.
   - The category is shown read-only: changing it is FR-17 (Could), a stretch item (PRD hard rule 6).
*/
import { del, get, post } from './api.js';

/* ---------- icons (from the design) ---------- */
const P = {
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>', pencil: '<path d="M4 20l4-1 11-11-3-3L5 16z"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>', refresh: '<path d="M20 11a8 8 0 1 0-2 6M20 4v7h-7"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>', ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v5H5V6h5"/>',
  spark: '<path d="M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z"/>', check: '<path d="m5 12 5 5 9-10"/>',
  alert: '<path d="M12 4l9 16H3zM12 10v4M12 17v.5"/>',
  lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  flag: '<path d="M6 21V4M6 5h11l-2 4 2 4H6"/>', tag: '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="8.5" r="1"/>',
  wifi: '<path d="M3 3l18 18M5 10a10 10 0 0 1 4-2.5M19 10a10 10 0 0 0-4-2.5M8.5 14a5 5 0 0 1 3.5-1.5M12 18h.01"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
  eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  move: '<path d="M12 3v18M3 12h18M8 7l4-4 4 4M8 17l4 4 4-4"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8v.5"/>',
  chev: '<path d="m9 6 6 6-6 6"/>', cal: '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/>',
  up: '<path d="m6 14 6-6 6 6"/>', down: '<path d="m6 10 6 6 6-6"/>', list: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  grid: '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
  all: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M7 12h10"/>',
  db: '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
  monitor: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
};
const ic = (n, c = '') => `<svg class="i ${c}" viewBox="0 0 24 24" aria-hidden="true">${P[n] || ''}</svg>`;

/* ---------- helpers ---------- */
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
const reEsc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const LOCALE = 'en-US'; // English labels; no timeZone option, so the browser's local zone is used
const fd = d => d ? new Date(d).toLocaleDateString(LOCALE, { month: 'short', day: 'numeric', year: 'numeric' }) : '–';
const ft = d => new Date(d).toLocaleTimeString(LOCALE, { hour: 'numeric', minute: '2-digit' });
const fdt = d => d ? `${fd(d)} · ${ft(d)}` : '–';
function rel(d) {
  if (!d) return 'never';
  const m = Math.round((Date.now() - new Date(d)) / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return h === 1 ? '1 hour ago' : `${h} hours ago`;
  const dd = Math.round(h / 24);
  return dd < 30 ? (dd === 1 ? '1 day ago' : `${dd} days ago`) : fd(d);
}
function fsize(b) {
  if (b == null) return '–';
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${Math.max(1, Math.round(b / 1024))} KB`;
  return `${(b / 1048576).toFixed(1).replace(/\.0$/, '')} MB`;
}
const pad = n => String(n).padStart(2, '0');
const ymd = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const cap = s => s ? s[0].toUpperCase() + s.slice(1) : s;
const KIND = { '.pdf': 'PDF', '.docx': 'Word', '.pptx': 'PowerPoint', '.txt': 'Text' };
const EXTL = { '.pdf': 'PDF', '.docx': 'Word', '.pptx': 'Slides', '.txt': 'Text' };
const extCls = e => ({ '.pdf': 'pdf', '.docx': 'docx', '.pptx': 'pptx' }[e] || 'txt');
const extTxt = e => (e || '').replace('.', '').toUpperCase().slice(0, 4);
const SEP = /[\\/]/;
const baseName = p => String(p || '').split(SEP).filter(Boolean).pop() || String(p || '');
const dirName = p => String(p || '').replace(/[\\/][^\\/]*$/, '');
const normP = p => String(p || '').replace(/\//g, '\\').replace(/\\+$/, '').toLowerCase();
const inDir = (path, dir) => normP(path).startsWith(normP(dir) + '\\');
const sepOf = p => (p.includes('\\') || !p.includes('/')) ? '\\' : '/';
const REASON = {
  no_text: ['No readable text', 'The file has no text to read. OCR for scans is a stretch feature.'],
  password_protected: ['Password protected', "Peekr can't open locked files, so this one was skipped."],
  too_large: ['Too large', 'The file is over the size limit set in config.yaml.'],
  extract_failed: ['Could not read', 'The file looks corrupt. Indexing carried on without it.'],
  file_locked: ['In use by another app', 'Peekr retried once, then marked it as an error.'],
  internal: ['Unexpected error', 'Peekr logged the error and carried on.'],
};
const reasonOf = r => REASON[r] || [r || 'Unknown', 'Peekr recorded this file and carried on.'];
const STOP = new Set(('yung na ang ng sa ko mga ay at para tungkol about the a an of my file files akin lang po paki hanapin ' +
  'find show nung noong last this in from is to and ba ano pdf pdfs word docx doc document documents slides pptx ppt ' +
  'powerpoint txt text month week year today yesterday folder buwan linggo taon nakaraang kahapon ngayon').split(' '));
const queryTerms = q => [...new Set((q.toLowerCase().match(/[\p{L}\p{N}]+/gu) || []).filter(t => t.length >= 3 && !STOP.has(t)))];
function hl(text, terms) {
  if (!terms.length) return esc(text);
  const re = new RegExp(`(${terms.map(reEsc).join('|')})`, 'giu');
  return String(text).split(re).map((part, i) => i % 2 ? `<mark>${esc(part)}</mark>` : esc(part)).join('');
}
const level = s => !s ? 0 : s >= 0.025 ? 3 : s >= 0.014 ? 2 : 1;
const LEVEL = ['', 'Possible', 'Good', 'Strong'];
const bars = l => l
  ? `<span class="match" title="Match strength">${[1, 2, 3].map(i => `<s class="${i <= l ? 'on' : ''}"></s>`).join('')}<span class="ml">${LEVEL[l]}</span></span>`
  : '<span class="muted">–</span>';
const errText = e => (e && e.message) || 'Something went wrong.';

/* ---------- dates (browser local time; same machine as the server's parser) ---------- */
const day0 = d => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const addD = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
function presets() {
  const t = day0(new Date()), mon = addD(t, -((t.getDay() + 6) % 7)), y = t.getFullYear(), m = t.getMonth();
  return [['Today', t, addD(t, 1)], ['Yesterday', addD(t, -1), t], ['This week', mon, addD(mon, 7)],
    ['Last week', addD(mon, -7), mon], ['This month', new Date(y, m, 1), new Date(y, m + 1, 1)],
    ['Last month', new Date(y, m - 1, 1), new Date(y, m, 1)], ['This year', new Date(y, 0, 1), new Date(y + 1, 0, 1)],
    ['Last year', new Date(y - 1, 0, 1), new Date(y, 0, 1)]];
}
const MENU_DATES = ['Today', 'Yesterday', 'This week', 'Last week', 'This month', 'Last month', 'Last year'];
function dateLabel(fromIso, toIso) {
  const a = new Date(fromIso), b = new Date(toIso);
  const p = presets().find(([, x, y]) => +x === +a && +y === +b);
  if (p) return p[0];
  const midnight = a.getHours() === 0 && a.getMinutes() === 0;
  if (midnight && a.getDate() === 1 && +new Date(a.getFullYear(), a.getMonth() + 1, 1) === +b)
    return a.toLocaleDateString(LOCALE, { month: 'long', year: 'numeric' });
  if (midnight && +addD(a, 1) === +b) return fd(a);
  return `${fd(a)} – ${fd(new Date(+b - 1))}`;
}

/* ---------- state ---------- */
const store = (() => { try { return window.localStorage; } catch { return null; } })();
const S = {
  view: 'files', health: null, offline: false, categories: [], folders: [], files: [], bad: [], byId: new Map(),
  job: null, loaded: false, libErr: null, libSig: null,
  q: '', ignore: new Set(), ignoredLabels: {}, parsedFor: null, dateSel: null, dateOpen: false, themeOpen: false,
  dFrom: '', dTo: '', search: { key: null, loading: false, res: null, err: null }, browseSnips: {}, locById: {},
  scope: { folder: null, cat: null }, collapsed: {}, sort: { k: null, dir: -1 },
  mode: (store && store.getItem('peekr-mode')) === 'tiles' ? 'tiles' : 'details', order: [],
  sel: null, tok: 0, ptab: 'details', meta: null, metaErr: null, hist: null, histErr: null, sum: null, selLoc: null,
  addOpen: false, addPath: '', addErr: '', adding: false, picking: false,
  removing: null, exclOpen: null, exclErr: '', busy: false,
  evFilter: 'all', events: null, eventsErr: null,
};
const jobActive = () => !!S.job && (S.job.state === 'running' || S.job.state === 'queued');
const aiOk = () => !!S.health && S.health.ollama_ok && S.health.llm_ready;

/* ---------- painting: only touch the DOM when the HTML changed, keep focus and typing ---------- */
const painted = new WeakMap();
function focusKey(a) {
  if (!a || a === document.body) return null;
  if (a.id) return `#${a.id}`;
  const d = a.dataset || {};
  return d.act ? `${d.act}|${d.id || d.k || d.p || d.v || d.c || d.t || d.m || d.l || ''}` : null;
}
function paint(el, html) {
  if (!el || painted.get(el) === html) return;
  const a = document.activeElement, key = a && el.contains(a) ? focusKey(a) : null;
  const typing = key && a.tagName === 'INPUT' && a.type !== 'date' ? [a.value, a.selectionStart, a.selectionEnd] : null;
  el.innerHTML = html;
  painted.set(el, html);
  if (!key) return;
  const n = key[0] === '#' ? el.querySelector(key) : [...el.querySelectorAll('[data-act]')].find(x => focusKey(x) === key);
  if (!n) return;
  n.focus({ preventScroll: true });
  if (typing && n.tagName === 'INPUT') { n.value = typing[0]; try { n.setSelectionRange(typing[1], typing[2]); } catch { /* not a text input */ } }
}
let toastTimer = 0;
function toast(msg, err) {
  const t = $('toast');
  t.textContent = msg;
  t.className = 'toast on' + (err ? ' err' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.className = 'toast'; }, err ? 5000 : 3200);
}

/* ---------- derived data ---------- */
function catNames() {
  const names = S.categories.map(c => c.name);
  for (const f of S.files) if (f.category && !names.includes(f.category)) names.push(f.category);
  return names;
}
function ccls(c) {
  if (!c || c === 'Other') return 'c6';
  const i = S.categories.findIndex(x => x.name === c);
  return i < 0 ? 'c6' : `c${(i % 6) + 1}`;
}
const catChip = c => c ? `<span class="cat ${ccls(c)}">${esc(c)}</span>` : '<span class="muted">–</span>';
function buildTree() {
  const sortKids = n => { n.kids.sort((a, b) => a.name.localeCompare(b.name)); n.kids.forEach(sortKids); };
  return S.folders.map(fo => {
    const sep = sepOf(fo.path), rootPath = fo.path.replace(/[\\/]+$/, '');
    const root = { name: baseName(fo.path), path: fo.path, avail: fo.available, kids: [] };
    for (const f of S.files) {
      if (f.folder_id !== fo.id || !inDir(f.path, fo.path)) continue;
      let cur = root, p = rootPath;
      for (const part of f.folder.slice(rootPath.length).split(SEP).filter(Boolean)) {
        p += sep + part;
        let n = cur.kids.find(k => k.name === part);
        if (!n) { n = { name: part, path: p, avail: fo.available, kids: [] }; cur.kids.push(n); }
        cur = n;
      }
    }
    sortKids(root);
    return root;
  });
}
const rootOf = path => S.folders.find(fo => normP(fo.path) === normP(path) || inDir(path, fo.path));
function shortLoc(folder) {
  const root = rootOf(folder);
  if (!root) return folder;
  const parent = dirName(root.path.replace(/[\\/]+$/, ''));
  return `…${sepOf(root.path)}${folder.slice(parent.length).replace(/^[\\/]+/, '')}`;
}
const fileCountIn = path => S.files.filter(f => inDir(f.path, path)).length;
const needsSearch = () => !!(S.q.trim() || S.dateSel);
const scoped = () => !!(S.scope.folder || S.scope.cat);
const keepScope = f => (!S.scope.cat || f.category === S.scope.cat) && (!S.scope.folder || inDir(f.path, S.scope.folder));

/* ---------- chrome ---------- */
function renderNav() {
  const files = S.view === 'files';
  const go = (k, l, i) => `<button class="ni" data-act="nav" data-v="${k}" aria-current="${S.view === k}">${ic(i, 'sm')}<span class="lbl">${l}</span></button>`;
  const treeHTML = (nodes, depth) => nodes.map(n => {
    const has = n.kids.length > 0, open = !S.collapsed[n.path];
    return `<div><button class="ni ${n.avail ? '' : 'unavail'}" style="padding-left:${10 + depth * 14}px" data-act="scope-folder" data-p="${esc(n.path)}" aria-current="${files && S.scope.folder === n.path}"${has ? ` aria-expanded="${open}"` : ''}>
      ${has ? `<span class="chev ${open ? 'open' : ''}" data-act="tree-toggle" data-p="${esc(n.path)}" role="button" aria-label="${open ? 'Collapse' : 'Expand'} ${esc(n.name)}">${ic('chev')}</span>` : '<span class="sp"></span>'}
      <span class="fo">${ic(n.avail ? 'folder' : 'alert', 'sm')}</span><span class="lbl" title="${esc(n.path)}">${esc(n.name)}</span>${n.avail ? `<span class="n">${fileCountIn(n.path)}</span>` : '<span class="sr-only">(drive not connected)</span>'}</button>
      ${has && open ? treeHTML(n.kids, depth + 1) : ''}</div>`;
  }).join('');
  const tree = buildTree();
  paint($('navpane'), `
  <div class="navgrp"><div class="navhd">Library</div>
    <button class="ni" data-act="scope-all" aria-current="${files && !S.scope.folder && !S.scope.cat}">${ic('all', 'sm')}<span class="lbl">All indexed files</span><span class="n">${S.files.length}</span></button></div>
  <div class="navgrp"><div class="navhd">Categories</div>${catNames().map(c => `<button class="ni" data-act="scope-cat" data-c="${esc(c)}" aria-current="${files && S.scope.cat === c}"><span class="dot d${ccls(c).slice(1)}"></span><span class="lbl">${esc(c)}</span><span class="n">${S.files.filter(f => f.category === c).length}</span></button>`).join('')}</div>
  <div class="navgrp tree"><div class="navhd">Indexed folders</div>${tree.length ? treeHTML(tree, 0) : '<div class="ni muted">No folders yet</div>'}</div>
  <div class="navgrp"><div class="navhd">Peekr</div>${go('folders', 'Manage folders', 'db')}${go('activity', 'Activity', 'activity')}${go('status', 'Status &amp; privacy', 'shield')}</div>
  <div class="navfoot"><b>${ic('shield', 'sm')}Local only</b>Peekr reads your folders but never changes them. Your file manager stays separate.</div>`);
}

let crumbFns = [];
function renderAddress() {
  const parts = [['Peekr', () => setScope(null, null)]];
  if (S.view === 'files') {
    const root = S.scope.folder && rootOf(S.scope.folder);
    if (root) {
      const sep = sepOf(root.path);
      let acc = root.path.replace(/[\\/]+$/, '');
      const accRoot = acc;
      parts.push([baseName(root.path), () => setScope(accRoot, null)]);
      for (const seg of S.scope.folder.slice(acc.length).split(SEP).filter(Boolean)) {
        acc += sep + seg;
        const p = acc;
        parts.push([seg, () => setScope(p, null)]);
      }
    } else if (S.scope.cat) parts.push([`${S.scope.cat} files`, null]);
    else parts.push(['All indexed files', null]);
  } else parts.push([{ folders: 'Manage folders', activity: 'Activity', status: 'Status & privacy' }[S.view], null]);
  crumbFns = parts.map(x => x[1]);
  paint($('address'), parts.map(([l], i) => `${i ? '<span class="sep" aria-hidden="true">›</span>' : ''}<button data-act="crumb" data-i="${i}" class="${i === parts.length - 1 ? 'last' : ''}"${i === parts.length - 1 ? ' aria-current="page"' : ''}>${esc(l)}</button>`).join(''));
}

function renderCmd() {
  const el = $('cmdbar'), busy = jobActive() || !S.folders.length;
  const f = S.sel && S.meta, canOpen = !!f && f.status !== 'deleted';
  if (S.view === 'files') {
    paint(el, `<button class="cmd primary" data-act="add-open">${ic('plus', 'sm')}Add folder</button><button class="cmd" data-act="rescan" ${busy ? 'disabled' : ''}>${ic('refresh', 'sm')}Rescan</button><span class="vsep"></span>
    <button class="cmd" data-act="open-os" ${canOpen ? '' : 'disabled'}>${ic('ext', 'sm')}Open file</button><button class="cmd" data-act="open-folder" ${canOpen ? '' : 'disabled'}>${ic('folder', 'sm')}Open folder</button><span class="grow"></span>
    <div class="seg" role="group" aria-label="View"><button data-act="mode" data-m="details" aria-pressed="${S.mode === 'details'}">${ic('list', 'sm')}Details</button><button data-act="mode" data-m="tiles" aria-pressed="${S.mode === 'tiles'}">${ic('grid', 'sm')}Tiles</button></div>`);
  } else if (S.view === 'folders') {
    paint(el, `<button class="cmd primary" data-act="add-toggle" aria-expanded="${S.addOpen}">${ic('plus', 'sm')}Add folder</button><button class="cmd" data-act="rescan" ${busy ? 'disabled' : ''}>${ic('refresh', 'sm')}Rescan all</button>`);
  } else if (S.view === 'activity') {
    const n = S.folders.filter(x => x.available && x.enabled).length;
    paint(el, `<span class="muted" style="padding:0 6px">History starts when a folder is first indexed.</span><span class="grow"></span><span class="pill ${n ? 'ok' : ''}"><i></i>Watching ${n} ${n === 1 ? 'folder' : 'folders'}</span>`);
  } else paint(el, '<span class="muted" style="padding:0 6px">Everything here works with the network off.</span>');
}

function renderBanner() {
  const h = S.health, b = [];
  if (S.offline) b.push(['bad', "Peekr's local server isn't responding. Check that the run.bat window is still open.", 'retry-all', 'Try again']);
  else if (h) {
    if (!h.db_ok) b.push(['bad', "Peekr can't write to its data folder. Check the free disk space and the folder permissions."]);
    if (!h.embedder_ready) b.push(h.embedder_error
      ? ['bad', 'The search model is missing, so search and indexing are blocked. While online, run <code>python -m app.ai.embedder --download</code> once, then restart Peekr.']
      : ['info', 'The search model is loading. Search and indexing start in a moment.']);
    if (!h.ollama_ok) b.push(['warn', "Ollama isn't running. Search still works. Summaries will show the first part of each file instead.", 'ollama-retry', 'Check again']);
    else if (!h.llm_ready) b.push(['warn', `The model ${esc(h.llm_model)} isn't installed in Ollama. Run <code>ollama pull ${esc(h.llm_model)}</code>. Until then, summaries show the first part of each file.`, 'ollama-retry', 'Check again']);
  }
  paint($('banner'), b.map(([cls, msg, act, lbl]) => `<div class="banner ${cls}" role="${cls === 'bad' ? 'alert' : 'status'}">${ic(cls === 'info' ? 'info' : 'alert')}<span>${msg}</span>${act ? `<button class="btn sm" data-act="${act}">${lbl}</button>` : ''}</div>`).join(''));
}

function renderStatusBar() {
  const h = S.health, j = S.job;
  let left = '';
  if (S.view === 'files') {
    const n = S.order.length, f = S.sel && S.meta;
    left = `<span class="it">${n} ${n === 1 ? 'item' : 'items'}</span>${f ? `<span class="it">1 selected · ${fsize(f.size_bytes)}</span>` : ''}`;
  } else if (S.view === 'folders') left = `<span class="it">${S.folders.length} ${S.folders.length === 1 ? 'folder' : 'folders'}</span>`;
  else if (S.view === 'activity' && S.events) left = `<span class="it">${S.events.length} events</span>`;
  const pills = [];
  if (jobActive()) pills.push(`<span class="pill acc"><i></i>${j.state === 'queued' ? 'Indexing queued' : `Indexing ${j.processed}/${j.total}`}</span>`);
  if (S.offline) pills.push('<span class="pill bad"><i></i>Server not responding</span>');
  else if (!h) pills.push('<span class="pill"><i></i>Checking…</span>');
  else {
    pills.push(h.ollama_ok && h.llm_ready ? '<span class="pill ok"><i></i>Ollama running</span>'
      : h.ollama_ok ? '<span class="pill warn"><i></i>Model missing</span>' : '<span class="pill bad"><i></i>Ollama stopped</span>');
    pills.push(h.embedder_ready ? '<span class="pill ok"><i></i>Embeddings ready</span>'
      : h.embedder_error ? '<span class="pill bad"><i></i>Embeddings missing</span>' : '<span class="pill acc"><i></i>Embeddings loading</span>');
  }
  pills.push(`<span class="pill ok">${ic('wifi', 'sm')}Works offline · 127.0.0.1 only</span>`);
  paint($('statusbar'), `${left}<span class="sp"></span>${pills.join('')}`);
}

function renderDate() {
  const cur = S.dateSel ? S.dateSel.label : null;
  if (!S.dFrom) { const t = new Date(); S.dFrom = ymd(new Date(t.getFullYear(), t.getMonth(), 1)); S.dTo = ymd(t); }
  paint($('datewrap'), `<button class="datebtn ${cur ? 'on' : ''}" data-act="date-toggle" aria-haspopup="true" aria-expanded="${S.dateOpen}">${ic('cal', 'sm')}<span>${cur ? esc(cur) : 'Any date'}</span>${ic('down', 'sm')}</button>${S.dateOpen ? `<div class="datemenu" role="menu" aria-label="Filter by date">
    <div class="hd">Created or modified</div>
    <button class="opt" role="menuitemradio" aria-checked="${!cur}" data-act="date-clear">Any date</button>
    ${MENU_DATES.map(o => `<button class="opt" role="menuitemradio" aria-checked="${cur === o}" data-act="date-pick" data-l="${o}">${o}</button>`).join('')}
    <hr><div class="hd">Custom range</div>
    <div class="rng"><label for="dfrom">From<input type="date" id="dfrom" value="${S.dFrom}"></label><label for="dto">To<input type="date" id="dto" value="${S.dTo}"></label></div>
    <button class="btn primary sm apply" data-act="date-custom">Apply range</button></div>` : ''}`);
}

const THEMES = { light: ['Light', 'sun'], dark: ['Dark', 'moon'], system: ['System', 'monitor'] };
function renderTheme() {
  const p = window.PeekrTheme.get(), [lbl, icon] = THEMES[p];
  paint($('themewrap'), `<button class="datebtn iconly" data-act="theme-toggle" aria-haspopup="true" aria-expanded="${S.themeOpen}" aria-label="Theme: ${lbl}" title="Theme: ${lbl}">${ic(icon, 'sm')}${ic('down', 'sm')}</button>${S.themeOpen ? `<div class="datemenu thememenu" role="menu" aria-label="Theme">
    <div class="hd">Theme</div>
    ${Object.entries(THEMES).map(([k, [l, i]]) => `<button class="opt" role="menuitemradio" aria-checked="${p === k}" data-act="theme-pick" data-k="${k}"><span>${ic(i, 'sm')}${l}</span>${k === 'system' ? `<small>${window.PeekrTheme.systemDark() ? 'Dark now' : 'Light now'}</small>` : ''}</button>`).join('')}</div>` : ''}`);
}

/* ---------- files view ---------- */
const MCOLS = [['name', 'Name', 'h-name'], ['loc', 'Location', 'h-loc'], ['cat', 'Category', 'h-cat'], ['mod', 'Date modified', 'h-mod'], ['size', 'Size', 'h-size'], ['match', 'Match', 'h-match']];
const SORTV = { name: x => x.f.name.toLowerCase(), loc: x => (x.f.folder || '').toLowerCase(), cat: x => x.f.category || '', mod: x => +new Date(x.f.modified_at), size: x => x.f.size_bytes ?? -1, match: x => x.s };
const EXAMPLES = ['resibo ng kuryente', 'slides tungkol sa ER diagram', 'form para sa enrollment', 'itinerary Baguio', 'yung PDF about normalization na dinownload ko last month'];

function listModel() {
  if (!needsSearch()) return { mode: 'browse', items: S.files.filter(keepScope).map(f => ({ f, s: 0, sn: S.browseSnips[f.id] || '', loc: null })) };
  const r = S.search.res;
  if (!r) return { mode: 'search', items: [], res: null };
  const items = r.results.map(x => {
    const lib = S.byId.get(x.file_id) || {};
    return { f: { ...lib, id: x.file_id, name: x.name, extension: x.extension, path: x.path, folder: x.folder, category: x.category, modified_at: x.modified_at, size_bytes: lib.size_bytes ?? null, created_at: lib.created_at ?? null }, s: x.score, sn: x.snippet, loc: x.location };
  }).filter(x => keepScope(x.f));
  return { mode: 'search', items, res: r };
}
function sortItems(items, ranked) {
  const k = S.sort.k || (ranked ? 'match' : 'mod'), dir = S.sort.k ? S.sort.dir : -1;
  if (k === 'match' && !S.sort.k) return items; // server ranking order
  return items.map((x, i) => [x, i]).sort(([a, i], [b, j]) => {
    const A = SORTV[k](a), B = SORTV[k](b);
    return ((A < B ? -1 : A > B ? 1 : 0) * dir) || i - j;
  }).map(([x]) => x);
}
function chipModel() {
  const chips = [];
  const parsed = S.parsedFor && S.parsedFor.q === S.q ? S.parsedFor.parsed : null;
  if (parsed) {
    if (parsed.extensions && parsed.extensions.length && !S.ignore.has('extensions')) chips.push(['extensions', parsed.extensions.map(e => EXTL[e] || e).join(' / '), false]);
    if (parsed.date_from && !S.dateSel && !S.ignore.has('date')) chips.push(['date', dateLabel(parsed.date_from, parsed.date_to), false]);
    if (parsed.folder_hint && !S.ignore.has('folder')) chips.push(['folder', `In ${cap(parsed.folder_hint)}`, false]);
  }
  if (S.dateSel) chips.push(['date', S.dateSel.label, false]);
  for (const k of S.ignore) if (S.ignoredLabels[k]) chips.push([k, S.ignoredLabels[k], true]);
  const order = { extensions: 0, date: 1, folder: 2 };
  return chips.sort((a, b) => order[a[0]] - order[b[0]]);
}
function emptyNoIndex() {
  if (jobActive()) return `<div class="empty"><h3>Peekr is reading your folders</h3><p>${S.job.state === 'queued' ? 'Indexing starts in a moment.' : `${S.job.processed} of ${S.job.total} files so far.`} Files become searchable as soon as they are indexed.</p></div>`;
  if (S.folders.length) return `<div class="empty"><h3>No searchable files yet</h3><p>Peekr found nothing it can read in your folders yet. Skipped files are listed in Manage folders.</p><button class="btn" data-act="nav" data-v="folders">${ic('db', 'sm')}Manage folders</button></div>`;
  return `<div class="empty"><h3>Nothing is indexed yet</h3><p>Add a folder and Peekr will read it so you can search.</p><button class="btn primary" data-act="add-open">${ic('plus', 'sm')}Add a folder</button></div>`;
}
const skeletonRows = msg => `<div class="skrows" aria-busy="true"><span class="sr-only">${esc(msg)}</span>${[0, 1, 2].map(() => '<div class="skel"><i style="width:42%"></i><i style="width:88%"></i></div>').join('')}</div>`;

function renderFiles() {
  if (S.view !== 'files' || !$('v-list')) return;
  const m = listModel(), ranked = m.mode === 'search' && !!S.q.trim(), terms = queryTerms(S.q);
  const chips = chipModel(), searching = !!(S.q.trim() || chips.length);
  const scopeChips = [];
  if (S.scope.cat) scopeChips.push(['cat', `Category: ${S.scope.cat}`]);
  if (S.scope.folder) scopeChips.push(['fol', `Folder: ${baseName(S.scope.folder)}`]);
  paint($('v-tools'), `<div class="listtools"><span class="lbl">${searching ? 'Search' : 'Try'}</span>
    ${searching ? '' : EXAMPLES.map(x => `<button class="chip" data-act="ex" data-l="${esc(x)}">${esc(x)}</button>`).join('')}
    ${chips.map(([k, l, off]) => `<span class="chip f ${off ? 'off' : ''}"><span class="t">${esc(l)}</span><button data-act="chip" data-k="${k}" data-l="${esc(l)}" aria-label="${off ? 'Turn on' : 'Remove'} filter ${esc(l)}">${ic(off ? 'plus' : 'x', 'sm')}</button></span>`).join('')}
    ${scopeChips.map(([k, l]) => `<span class="chip f"><span class="t">${esc(l)}</span><button data-act="unscope" data-k="${k}" aria-label="Clear ${esc(l)}">${ic('x', 'sm')}</button></span>`).join('')}
    ${S.q.trim() ? `<button class="chip" data-act="clearq">${ic('x', 'sm')}Clear search</button>` : ''}</div>`);

  let h = '';
  S.order = [];
  S.locById = {};
  if (!S.loaded) h = skeletonRows('Loading your library');
  else if (m.mode === 'browse' && S.libErr && !S.files.length) h = `<div class="empty"><h3>Can't load your library</h3><p>${esc(errText(S.libErr))}</p><button class="btn" data-act="retry-all">${ic('refresh', 'sm')}Try again</button></div>`;
  else if (m.mode === 'search' && !m.res && S.search.loading) h = skeletonRows('Searching on this laptop');
  else if (m.mode === 'search' && S.search.err) {
    const e = S.search.err;
    const title = e.code === 'embedder_not_ready' ? "The search model isn't ready" : e.code === 'network' ? "Peekr's server isn't responding" : 'Search failed';
    h = `<div class="empty" role="alert"><h3>${title}</h3><p>${esc(errText(e))}</p><button class="btn" data-act="retry-search">${ic('refresh', 'sm')}Try again</button></div>`;
  } else if ((m.mode === 'search' && m.res && m.res.reason === 'no_indexed_files') || (m.mode === 'browse' && !S.files.length)) h = emptyNoIndex();
  else {
    if (m.res && m.res.relaxed_filters) h += `<div class="note">${ic('info')}No exact match for every filter, so Peekr loosened the folder or date filter.</div>`;
    const list = sortItems(m.items, ranked);
    S.order = list.map(x => x.f.id);
    list.forEach(x => { S.locById[x.f.id] = x.loc; });
    if (!list.length) {
      h += m.mode === 'search'
        ? '<div class="empty"><h3>No matching files</h3><p>Try fewer words, or describe what\'s inside instead of the file name.</p></div>'
        : '<div class="empty"><h3>No files here yet</h3><p>Nothing indexed matches this category or folder.</p></div>';
    } else if (S.mode === 'details') {
      const sk = S.sort.k || (ranked ? 'match' : 'mod'), dir = S.sort.k ? S.sort.dir : -1;
      h += `<div role="grid" aria-label="Files" aria-busy="${S.search.loading}"><div class="thead" role="row">${MCOLS.map(([k, l, c]) => `<button class="${c}" data-act="sort" data-k="${k}" role="columnheader" ${sk === k ? `aria-sort="${dir > 0 ? 'ascending' : 'descending'}"` : ''}>${l}${ic(sk === k && dir > 0 ? 'up' : 'down', 'sm')}</button>`).join('')}</div>`;
      h += list.map(({ f, s, sn }) => `<div class="trow" role="row" tabindex="0" data-act="select" data-id="${f.id}" aria-selected="${S.sel === f.id}">
        <div class="c-name" role="gridcell"><span class="fi ${extCls(f.extension)}" aria-hidden="true">${extTxt(f.extension)}</span><div style="min-width:0"><div class="nm">${esc(f.name)}</div>${sn ? `<div class="sn">${hl(sn, terms)}</div>` : ''}</div></div>
        <div class="c-loc mono" role="gridcell" title="${esc(f.folder)}">${esc(shortLoc(f.folder))}</div>
        <div class="c-cat" role="gridcell">${catChip(f.category)}</div>
        <div class="c-mod" role="gridcell">${fd(f.modified_at)}</div><div class="c-size" role="gridcell">${fsize(f.size_bytes)}</div><div class="c-match" role="gridcell">${bars(ranked ? level(s) : 0)}</div></div>`).join('') + '</div>';
    } else {
      h += `<div class="tiles" aria-busy="${S.search.loading}">${list.map(({ f, s, sn }) => `<button class="tile" data-act="select" data-id="${f.id}" aria-selected="${S.sel === f.id}"><div class="top"><span class="fi lg ${extCls(f.extension)}" aria-hidden="true">${extTxt(f.extension)}</span><div style="min-width:0"><div class="nm">${esc(f.name)}</div>${catChip(f.category)}</div></div>${sn ? `<div class="sn">${hl(sn, terms)}</div>` : ''}<div class="meta"><span>${fd(f.modified_at)}</span><span>${fsize(f.size_bytes)}</span>${bars(ranked ? level(s) : 0)}</div></button>`).join('')}</div>`;
    }
  }
  paint($('v-list'), h);
  renderStatusBar();
}

/* ---------- preview pane (F4, F5, F7) ---------- */
function evInfo(e) {
  switch (e.event_type) {
    case 'baseline': return ['flag', 'Added to Peekr', 'History starts here. Earlier history is limited to file times.'];
    case 'created': return ['plus', 'Created', ''];
    case 'modified': return ['pencil', 'Content edited', 'The text changed, so Peekr read the file again.'];
    case 'moved': return ['move', 'Moved', `<div class="mono" style="overflow-wrap:anywhere">${esc(e.old_path)}<br>→ ${esc(e.new_path)}</div>`];
    case 'renamed': return ['tag', 'Renamed', `<div class="mono" style="overflow-wrap:anywhere">${esc(baseName(e.old_path))} → ${esc(baseName(e.new_path))}</div>`];
    case 'deleted': return ['trash', 'Deleted from disk', 'Kept in history. No longer searchable.'];
    default: return ['info', cap(e.event_type), ''];
  }
}
function timelineHTML(f) {
  if (!S.hist) return S.histErr
    ? `<div class="err">${ic('alert')}${esc(errText(S.histErr))}</div><button class="btn sm" data-act="retry-detail">${ic('refresh', 'sm')}Try again</button>`
    : '<div class="skel"><i style="width:70%"></i><i style="width:50%"></i><i style="width:64%"></i></div>';
  return `<ol class="timeline">${S.hist.map(e => {
    const [i, t, sub] = evInfo(e);
    return `<li><span class="tdot ${e.event_type}">${ic(i, 'sm')}</span><div><div class="tt">${t}</div>${sub ? `<div class="ts block">${sub}</div>` : ''}<div class="ts"><span>${fdt(e.occurred_at)}</span><span class="src">${esc(e.source)}</span>${e.source === 'reconcile' ? '<span>Found by a startup check or rescan. Exact time unknown.</span>' : ''}</div></div></li>`;
  }).join('')}
  <li><span class="tdot">${ic('file', 'sm')}</span><div><div class="tt">File times on disk</div><div class="ts"><span>Created ${fdt(f.created_at)}</span></div><div class="ts"><span>Modified ${fdt(f.modified_at)}</span></div></div></li></ol>`;
}
function summaryHTML(f) {
  if (f.status === 'deleted') return '<div class="sumcard"><p class="muted">This file was deleted from disk, so its summary was removed. Its history is kept.</p></div>';
  if (f.status !== 'indexed') return `<div class="sumcard"><p class="muted">${f.status === 'pending' ? 'Peekr has not read this file yet.' : "No summary: Peekr couldn't read text from this file."}</p></div>`;
  const st = S.sum;
  if (!st || st.st === 'loading') return `<div class="sumcard" aria-busy="true"><div class="skel"><i style="width:96%"></i><i style="width:90%"></i><i style="width:94%"></i><i style="width:60%"></i></div><div class="sumfoot">Reading the file on this laptop…</div></div>`;
  if (st.st === 'error') return `<div class="sumcard"><div class="err" role="alert">${ic('alert')}${esc(errText(st.err))}</div><div class="sumfoot"><span class="grow"></span><button class="btn sm" data-act="regen">${ic('refresh', 'sm')}Try again</button></div></div>`;
  const h = S.health;
  const why = !h || !h.ollama_ok ? 'Ollama is stopped. Showing the start of the file instead of an AI summary.'
    : !h.llm_ready ? `The model ${h.llm_model} isn't installed. Showing the start of the file instead of an AI summary.`
      : "The local AI didn't answer in time. Showing the start of the file instead of an AI summary.";
  const stale = st.cached && f.summary_cached === false;
  return `<div class="sumcard">${st.fallback ? `<div class="pill warn" style="margin-bottom:10px;white-space:normal">${ic('alert', 'sm')}${esc(why)}</div>` : ''}${st.summary ? `<p>${esc(st.summary)}</p>` : '<p class="muted">There is no text to summarize.</p>'}
  ${stale ? `<div class="pill warn" style="margin-top:10px;white-space:normal">${ic('info', 'sm')}The file changed after this summary was saved. Regenerate to update it.</div>` : ''}
  <div class="sumfoot">${st.fallback ? '<span class="tag">Preview only</span>' : st.cached ? '<span class="pill ok"><i></i>Saved summary · instant</span>' : `<span class="pill acc"><i></i>Just generated on this laptop · ${(st.elapsed_ms / 1000).toFixed(1)} s</span>`}${!st.fallback && st.model ? `<span>${esc(st.model)}</span>` : ''}<span class="grow"></span><button class="btn sm" data-act="regen" ${aiOk() ? '' : 'disabled title="Needs Ollama and the model"'}>${ic('refresh', 'sm')}Regenerate</button></div></div>`;
}
const STATUS_PILL = { indexed: ['ok', 'Indexed'], deleted: ['bad', 'Deleted'], skipped: ['warn', 'Skipped'], error: ['bad', 'Error'], pending: ['acc', 'Waiting'] };
function renderPreview() {
  const el = $('preview'), sc = $('scrim');
  if (!S.sel) {
    el.classList.remove('open'); sc.classList.remove('open');
    paint(el, `<div class="p-empty"><div class="ring">${ic('eye')}</div><b>Select a file to preview</b><p>See a summary, where it's saved, its category, and how it changed over time, without opening it.</p></div>`);
    return;
  }
  el.classList.add('open'); sc.classList.add('open');
  const f = S.meta;
  const close = `<button class="btn sm p-close" data-act="close-detail" aria-label="Close preview">${ic('x', 'sm')}</button>`;
  if (!f) {
    paint(el, S.metaErr
      ? `<div class="p-head"><div style="flex:1"></div>${close}</div><div class="p-empty" role="alert"><div class="ring">${ic('alert')}</div><b>Can't load this file</b><p>${esc(errText(S.metaErr))}</p><p><button class="btn sm" data-act="retry-detail">${ic('refresh', 'sm')}Try again</button></p></div>`
      : `<div class="p-head"><div style="flex:1"></div>${close}</div><div class="p-body"><div class="skel"><i style="width:60%"></i><i style="width:90%"></i><i style="width:75%"></i></div></div>`);
    return;
  }
  const gone = f.status === 'deleted', [pc, pl] = STATUS_PILL[f.status] || ['', f.status];
  const names = catNames();
  const body = S.ptab === 'details' ? `
    <div class="sec"><h3>Where it is</h3><div class="pathbox mono">${esc(f.path)}</div>
      <dl class="facts"><div><dt>Category</dt><dd><select class="catsel" disabled aria-label="Category (changing it is a stretch feature)" title="Changing the category is a stretch feature">${(f.category && !names.includes(f.category) ? [f.category, ...names] : names).map(c => `<option ${c === f.category ? 'selected' : ''}>${esc(c)}</option>`).join('')}${f.category ? '' : '<option selected>–</option>'}</select></dd></div><div><dt>Type</dt><dd>${KIND[f.extension] || esc(f.extension)}</dd></div><div><dt>Created</dt><dd>${fd(f.created_at)}</dd></div><div><dt>Modified</dt><dd>${fd(f.modified_at)}</dd></div><div><dt>Size</dt><dd>${fsize(f.size_bytes)}</dd></div><div><dt>Best match at</dt><dd>${esc(S.selLoc || '–')}</dd></div></dl>
      ${f.status === 'skipped' || f.status === 'error' ? `<div class="warnbox" style="margin-top:12px">${ic('alert', 'sm')}${esc(reasonOf(f.status_reason).join('. '))}</div>` : ''}</div>
    <div class="sec"><h3>${ic('spark', 'sm')}Summary</h3>${summaryHTML(f)}</div>
    <div class="sec"><h3>What changed</h3><div class="locked">${ic('lock')}<div><b>Short change note</b> <span class="tag">Stretch</span><div class="small">A one-line AI note comparing two versions will appear here after the MVP is stable.</div></div></div></div>`
    : `<div class="sec"><h3>Timeline <span class="live"><i></i>Refreshes every 3 s</span></h3>${timelineHTML(f)}</div>`;
  const prevBody = el.querySelector('.p-body'), top = prevBody ? prevBody.scrollTop : 0;
  paint(el, `
  <div class="p-head"><span class="fi lg ${extCls(f.extension)}" aria-hidden="true">${extTxt(f.extension)}</span>
    <div style="flex:1;min-width:0"><h2>${esc(f.name)}</h2><div class="row" style="margin-top:6px">${catChip(f.category)}<span class="pill ${pc}"><i></i>${esc(pl)}</span></div></div>${close}</div>
  <div class="p-actions"><button class="btn primary" data-act="open-os" ${gone ? 'disabled' : ''}>${ic('ext', 'sm')}Open file</button><button class="btn" data-act="open-folder" ${gone ? 'disabled' : ''}>${ic('folder', 'sm')}Open folder</button></div>
  <div class="tabs" role="tablist" aria-label="File details"><button role="tab" id="tab-details" data-act="ptab" data-t="details" aria-selected="${S.ptab === 'details'}" aria-controls="pbody">Details</button><button role="tab" id="tab-history" data-act="ptab" data-t="history" aria-selected="${S.ptab === 'history'}" aria-controls="pbody">History</button></div>
  <div class="p-body" id="pbody" role="tabpanel" aria-labelledby="tab-${S.ptab}">${body}</div>`);
  const nb = el.querySelector('.p-body');
  if (nb && nb !== prevBody) nb.scrollTop = top;
}

/* ---------- folders view (F2, F6) ---------- */
function renderFolders() {
  if (S.view !== 'folders' || !$('v-job')) return;
  const j = S.job || { state: 'idle', kind: 'none', total: 0, processed: 0, skipped: 0, errors: 0 };
  paint($('v-add'), S.addOpen ? `<div class="card addpanel"><div><b>Choose a folder to index</b><div class="muted">Pick it with the Windows dialog or paste a path. Subfolders are included.</div></div>
    <div class="field"><button class="btn" data-act="pick" ${S.picking || S.adding ? 'disabled' : ''}>${ic('folder', 'sm')}${S.picking ? 'Waiting for the dialog…' : 'Choose folder…'}</button><input id="addpath" aria-label="Folder path" placeholder="C:\\Users\\you\\Documents\\Thesis" value="${esc(S.addPath)}"><button class="btn primary" data-act="add" ${S.adding ? 'disabled' : ''}>${S.adding ? 'Adding…' : 'Add and index'}</button></div>
    ${S.addErr ? `<div class="err" role="alert">${ic('alert')}${esc(S.addErr)}</div>` : ''}
    <div class="muted small">System folders and folders already inside an added folder can't be added.</div></div>` : '');
  const STATE = { idle: ['', 'Idle'], queued: ['acc', 'Queued'], running: ['acc', 'Running'], done: ['ok', 'Finished'], failed: ['bad', 'Failed'] };
  const [sc, sl] = STATE[j.state] || ['', j.state];
  const pct = j.total ? Math.round(j.processed / j.total * 100) : j.state === 'done' ? 100 : 0;
  paint($('v-job'), `<div class="card pad">
    <div class="row between"><div><b>Indexing</b> <span class="pill ${sc}" style="margin-left:6px"><i></i>${sl}</span></div>${jobActive() ? `<span class="mono muted" style="overflow-wrap:anywhere">${esc(j.current_file || '')}</span>` : `<span class="muted">${j.kind === 'rescan' ? 'Last job: rescan' : j.kind === 'initial' ? 'Last job: first scan' : 'No job yet'}</span>`}</div>
    <div class="bar" style="margin:12px 0" role="progressbar" aria-label="Indexing progress" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"><b style="width:${pct}%"></b></div>
    <div class="stats"><div class="stat"><b>${j.processed}<small> / ${j.total}</small></b><span>Files processed</span></div><div class="stat"><b>${j.skipped}</b><span>Skipped</span></div><div class="stat"><b>${j.errors}</b><span>Errors</span></div></div>
    ${j.state === 'failed' ? `<div class="err" style="margin-top:12px" role="alert">${ic('alert')}${esc(j.error || 'The job stopped because of an unexpected error.')}</div>` : ''}
    <p class="muted small" style="margin:12px 0 0">Unchanged files are skipped on later scans, so rescans stay quick.</p></div>`);
  const busy = jobActive();
  paint($('v-folders'), S.folders.length ? S.folders.map(fo => {
    const n = S.files.filter(f => f.folder_id === fo.id).length, sep = sepOf(fo.path);
    return `<div class="card folder ${fo.available ? '' : 'unavail'}">
    <div class="folder-top"><div class="folder-ic">${ic(fo.available ? 'folder' : 'alert')}</div><div style="min-width:0;flex:1"><div class="p mono">${esc(fo.path)}</div><div class="muted small">${fo.available ? `${n} indexed ${n === 1 ? 'file' : 'files'} · ${fo.last_scan_at ? `last scan ${rel(fo.last_scan_at)}` : 'not scanned yet'}` : 'Drive not connected. Files are kept in the index and not marked deleted.'}</div></div>
    <span class="pill ${fo.available ? 'ok' : 'warn'}"><i></i>${fo.available ? 'Watching' : 'Unavailable'}</span></div>
    ${fo.exclusions && fo.exclusions.length ? `<div class="row"><span class="muted small">Excluded</span>${fo.exclusions.map(x => `<span class="chip mono" title="${esc(x)}">${esc(inDir(x, fo.path) ? '…' + sep + x.slice(fo.path.replace(/[\\/]+$/, '').length + 1) : x)}</span>`).join('')}</div>` : ''}
    ${S.exclOpen === fo.id ? `<div class="field"><input id="exclpath-${fo.id}" aria-label="Subfolder to exclude" placeholder="${esc(fo.path.replace(/[\\/]+$/, '') + sep)}Private"><button class="btn sm primary" data-act="excl-save" data-id="${fo.id}" ${S.busy ? 'disabled' : ''}>Exclude</button><button class="btn sm" data-act="excl-toggle" data-id="${fo.id}">Cancel</button></div>${S.exclErr ? `<div class="err" role="alert">${ic('alert')}${esc(S.exclErr)}</div>` : ''}` : ''}
    ${S.removing === fo.id ? `<div class="warnbox">${ic('alert', 'sm')}Remove from Peekr? Your files on disk are not touched. Peekr forgets their summaries and history.</div><div class="row"><button class="btn danger sm" data-act="remove-yes" data-id="${fo.id}" ${S.busy ? 'disabled' : ''}>Remove folder</button><button class="btn sm" data-act="remove-no">Keep it</button></div>`
      : `<div class="row"><button class="btn sm" data-act="rescan" data-id="${fo.id}" ${!fo.available || busy ? 'disabled' : ''}>${ic('refresh', 'sm')}Rescan</button><button class="btn sm" data-act="excl-toggle" data-id="${fo.id}" aria-expanded="${S.exclOpen === fo.id}">Exclude subfolder</button><span class="grow"></span><button class="btn sm danger" data-act="remove" data-id="${fo.id}">${ic('trash', 'sm')}Remove</button></div>`}</div>`;
  }).join('') : `<div class="card pad muted">No folders yet. Use <b>Add folder</b> to choose one.</div>`);
  paint($('v-skipped'), `<div class="card pad"><div class="row between" style="margin-bottom:6px"><b>Skipped files</b><span class="muted small">Peekr listed these and kept going.</span></div>
   ${S.bad.length ? `<div class="tablewrap"><table><thead><tr><th>File</th><th>Why</th></tr></thead><tbody>${S.bad.map(s => { const [t, d] = reasonOf(s.status_reason); return `<tr><td class="mono path">${esc(s.path)}</td><td><b>${esc(t)}</b> <span class="src">${esc(s.status_reason || s.status)}</span><div class="muted small">${esc(d)}</div></td></tr>`; }).join('')}</tbody></table></div>` : '<div class="muted">Nothing skipped.</div>'}</div>`);
  renderStatusBar();
}

/* ---------- activity view (F5) ---------- */
const EVF = ['all', 'created', 'modified', 'moved', 'renamed', 'deleted', 'baseline'];
function renderActivity() {
  if (S.view !== 'activity' || !$('v-events')) return;
  paint($('v-evf'), EVF.map(k => `<button class="chip" data-act="evf" data-k="${k}" aria-pressed="${S.evFilter === k}">${k === 'all' ? 'All' : cap(k)}</button>`).join(''));
  let h;
  if (S.events === null) h = S.eventsErr ? `<div class="empty" role="alert"><h3>Can't load activity</h3><p>${esc(errText(S.eventsErr))}</p><button class="btn" data-act="retry-events">${ic('refresh', 'sm')}Try again</button></div>` : skeletonRows('Loading activity');
  else if (!S.events.length) h = '<div class="empty">No events of this type yet.</div>';
  else h = S.events.map(e => {
    const [i, t] = evInfo(e);
    return `<button class="evrow" data-act="select-hist" data-id="${e.file_id}" data-k="${e.id}"><span class="tdot ${e.event_type}">${ic(i, 'sm')}</span><div style="min-width:0"><div class="tt" style="overflow-wrap:anywhere">${esc(e.name)} <span class="muted" style="font-weight:500">· ${t}</span></div><div class="ts"><span class="mono" style="overflow-wrap:anywhere">${esc(dirName(e.path))}</span></div></div><div class="ts when"><span>${fdt(e.occurred_at)}</span><span class="src">${esc(e.source)}</span></div></button>`;
  }).join('');
  paint($('v-events'), h);
  renderStatusBar();
}

/* ---------- status view (F1, FR-25) ---------- */
function renderStatusPage() {
  if (S.view !== 'status' || !$('v-status')) return;
  const h = S.health;
  const host = u => { try { return new URL(u).host; } catch { return u; } };
  const emb = h ? String(h.embedding_model).split('/').pop() : '';
  const hs = !h ? [['Ollama', 'wait', S.offline ? 'Server not responding.' : 'Checking…']] : [
    ['Ollama', h.ollama_ok ? 'ok' : 'bad', h.ollama_ok ? `Answering on ${host(h.ollama_url)}` : 'Not reachable. Summaries use the file preview.'],
    ['Language model', h.llm_ready ? 'ok' : 'bad', h.llm_ready ? `${h.llm_model} installed` : h.ollama_ok ? `${h.llm_model} is not installed. Run: ollama pull ${h.llm_model}` : `${h.llm_model} unavailable while Ollama is stopped`],
    ['Embedding model', h.embedder_ready ? 'ok' : h.embedder_error ? 'bad' : 'wait', h.embedder_ready ? `${emb} on ${String(h.embedding_device).toUpperCase()}` : h.embedder_error ? h.embedder_error : `${emb} is loading…`],
    ['Database', h.db_ok ? 'ok' : 'bad', h.db_ok ? 'SQLite, WAL mode, data folder writable' : "Can't write to the data folder."],
    ['Local only', h.local_only ? 'ok' : 'bad', 'No cloud AI, no telemetry, no CDN'],
  ];
  const metrics = [['Search accuracy', 'Correct file in top 3 for at least 70% of about 30 test queries'], ['Search response time', 'Under 3 seconds after indexing'], ['Summary time', 'Under 20 seconds, instant when saved'], ['Indexing speed', 'About 100 documents in under 10 minutes'], ['Offline operation', 'All core features pass with Wi-Fi off'], ['History correctness', 'Every create, edit, move, and rename is recorded']];
  paint($('v-status'), `
  <div class="hgrid">${hs.map(([a, st, b]) => `<div class="card health ${st === 'ok' ? '' : st}"><div class="hd">${ic(st === 'ok' ? 'check' : st === 'wait' ? 'info' : 'alert')}</div><div><b>${a}</b><small>${esc(b)}</small></div></div>`).join('')}</div>
  <div class="split">
   <div class="card pad"><h3 class="t">Privacy by design</h3>
    <ul class="list">
     <li>${ic('lock')}<div><b>Stays on 127.0.0.1</b><div class="muted">The app only accepts connections from this laptop, at ${esc(location.host)}.</div></div></li>
     <li>${ic('shield')}<div><b>Nothing is sent out</b><div class="muted">File content, file names, and search queries never leave the device.</div></div></li>
     <li>${ic('eye')}<div><b>Read-only access</b><div class="muted">Peekr never writes, moves, renames, or deletes your files. It writes only to its own data folder.</div></div></li>
     <li>${ic('wifi')}<div><b>Check it yourself</b><div class="muted">Turn Wi-Fi off, or open a network monitor, and use Peekr. Nothing should break and nothing should connect.</div></div></li></ul></div>
   <div class="card pad"><h3 class="t">Try a failure</h3><p class="muted" style="margin-top:0">See how Peekr behaves when the local AI stops.</p>
    <ul class="list">
     <li>${ic('alert')}<div><b>Quit Ollama</b><div class="muted">Close it from the system tray. Within about 5 seconds the banner appears and the Ollama pill turns red.</div></div></li>
     <li>${ic('search')}<div><b>Search still works</b><div class="muted">Summaries fall back to the first part of the file, with a notice.</div></div></li>
     <li>${ic('refresh')}<div><b>Start it again</b><div class="muted">Open Ollama, then choose Check again on the banner.</div></div></li></ul></div></div>
  <div class="card pad"><h3 class="t">Categories</h3><p class="muted" style="margin-top:0">Peekr files each document under one of these by comparing its meaning to the descriptions in config.yaml.</p>
   <div class="grid2" style="gap:10px">${S.categories.map(c => `<div class="catrow">${catChip(c.name)}<span class="muted small">${esc(c.description)}</span></div>`).join('')}</div>
   <div class="row" style="margin-top:12px"><span class="chip dim">Change a file's category <span class="tag">Stretch</span></span><span class="chip dim">Add or edit categories <span class="tag">Stretch</span></span></div></div>
  <div class="card pad"><div class="row between" style="margin-bottom:4px"><h3 class="t">Targets and measured results</h3><span class="muted small">Only real measurements from the demo laptop are filled in.</span></div>
   <div class="tablewrap"><table><thead><tr><th>Metric</th><th>Draft target</th><th>Measured</th></tr></thead><tbody>${metrics.map(([a, b]) => `<tr><td><b>${a}</b></td><td>${b}</td><td><span class="tag">Not measured yet</span></td></tr>`).join('')}</tbody></table></div></div>
  <div class="card pad"><h3 class="t">Memory budget (4 GB GPU)</h3>
   <div class="tablewrap"><table><thead><tr><th>Item</th><th>Runs on</th><th>Planned memory</th></tr></thead><tbody><tr><td>3B to 4B language model, 4-bit</td><td>GPU</td><td>About 2 to 3 GB</td></tr><tr><td>Embedding model</td><td>CPU</td><td>Well under 1 GB</td></tr><tr><td>OCR (stretch)</td><td>CPU</td><td>System RAM</td></tr><tr><td>Windows and display</td><td>GPU</td><td>About 0.3 to 0.5 GB</td></tr></tbody></table></div>
   <p class="muted small" style="margin-bottom:0">One model loaded at a time, one AI call at a time. Confirm by measuring on the demo laptop.</p></div>`);
}

/* ---------- routing ---------- */
function mountView() {
  const v = $('view');
  if (S.view === 'files') v.innerHTML = '<div id="v-tools"></div><div id="v-list"></div>';
  else if (S.view === 'folders') v.innerHTML = `<div class="page"><div class="page-head"><h1>Manage folders</h1><p>Peekr is separate from your file manager. It reads the folders you choose below, leaves them exactly as they are, and keeps its own index on this laptop.</p></div>
    <div id="v-add"></div><div id="v-job"></div><div id="v-folders" class="grid2"></div><div id="v-skipped"></div>
    <div class="card pad"><b>What Peekr can read</b><div class="row" style="margin-top:10px"><span class="chip">PDF</span><span class="chip">Word (.docx)</span><span class="chip">PowerPoint (.pptx)</span><span class="chip">Text (.txt)</span><span class="chip dim">Excel <span class="tag">Stretch</span></span><span class="chip dim">Scans &amp; images (OCR) <span class="tag">Stretch</span></span></div></div></div>`;
  else if (S.view === 'activity') v.innerHTML = `<div class="page"><div class="page-head"><h1>Activity</h1><p>A running record of what happened to your indexed files: created, edited, moved, renamed, or deleted. Select an event to open that file's full timeline.</p></div>
    <div class="card pad"><b>See it live</b><div class="muted" style="margin-top:2px">Peekr is read-only and watches your folders. Create, edit, rename, move, or delete a file in File Explorer and the event shows up here within a few seconds. A save fires several events, and Peekr waits 1.5 s to count it once.</div></div>
    <div class="row" id="v-evf" role="group" aria-label="Filter events"></div><div class="card clip" id="v-events"></div></div>`;
  else v.innerHTML = '<div class="page"><div class="page-head"><h1>Status &amp; privacy</h1><p>Proof that Peekr runs on this laptop. Everything here works with the network switched off.</p></div><div id="v-status" style="display:contents"></div></div>';
  v.scrollTop = 0;
}
function renderView() { renderFiles(); renderFolders(); renderActivity(); renderStatusPage(); }
function render() {
  renderNav(); renderAddress(); renderCmd(); renderBanner(); renderDate(); renderTheme();
  renderView(); renderPreview(); renderStatusBar();
}
function setView(v) {
  if (S.view !== v) { S.view = v; mountView(); }
  if (v === 'activity') loadEvents();
  render();
}
function setScope(folder, cat) {
  const wasScoped = scoped();
  S.scope = { folder, cat };
  if (S.view !== 'files') { S.view = 'files'; mountView(); }
  if (needsSearch() && wasScoped !== scoped()) runSearch(true);
  render();
}

/* ---------- data ---------- */
function netFail(e) {
  if (e && e.code === 'network' && !S.offline) { S.offline = true; renderBanner(); renderStatusBar(); renderStatusPage(); }
}
function netOk() {
  if (!S.offline) return;
  S.offline = false;
  renderBanner(); renderStatusBar();
  loadAll();
}
async function loadHealth() {
  try { S.health = await get('/api/health'); netOk(); } catch (e) { netFail(e); }
  renderBanner(); renderStatusBar(); renderStatusPage(); renderPreview();
}
async function loadCategories() {
  try { S.categories = (await get('/api/categories')).categories; netOk(); } catch (e) { netFail(e); }
}
async function loadLibrary() {
  try {
    const [fo, fi, bad] = await Promise.all([get('/api/folders'), get('/api/files'), get('/api/files?status=skipped,error')]);
    netOk();
    S.folders = fo.folders; S.files = fi.files; S.bad = bad.files; S.byId = new Map(S.files.map(f => [f.id, f])); S.libErr = null;
  } catch (e) { S.libErr = e; netFail(e); }
  S.loaded = true;
  const sig = S.files.map(f => `${f.id}:${f.modified_at}:${f.path}:${f.category}`).join('|');
  if (sig !== S.libSig) {
    S.libSig = sig;
    loadBrowseSnips();
    if (needsSearch()) runSearch(true);
  }
  renderNav(); renderAddress(); renderCmd(); renderView(); renderPreview(); renderStatusBar();
}
async function loadBrowseSnips() {
  if (!S.files.length) { S.browseSnips = {}; return; }
  try {
    const r = await post('/api/search', { query: '', limit: 100 });
    S.browseSnips = Object.fromEntries(r.results.map(x => [x.file_id, x.snippet]));
  } catch { /* snippets are optional in the browse list */ }
  renderFiles();
}
async function loadAll() { await Promise.all([loadHealth(), loadCategories(), pollIndex()]); await loadLibrary(); }
async function pollIndex() {
  let j;
  try { j = await get('/api/index/status'); netOk(); } catch (e) { netFail(e); return; }
  const prev = S.job;
  S.job = j;
  const wasActive = prev && (prev.state === 'running' || prev.state === 'queued');
  const nowActive = jobActive();
  if (prev && !nowActive && (wasActive || prev.job_id !== j.job_id) && j.job_id != null) {
    if (j.state === 'failed') toast(`Indexing stopped: ${j.error || 'unexpected error'}`, true);
    else if (j.state === 'done') toast(j.kind === 'rescan' ? 'Rescan finished.' : 'Indexing finished. Search is ready.');
    loadLibrary();
  }
  renderCmd(); renderFolders(); renderStatusBar();
  if (S.view === 'files' && (!S.files.length || wasActive !== nowActive)) renderFiles();
}
async function loadEvents() {
  try {
    const r = await get(`/api/events?limit=200${S.evFilter === 'all' ? '' : `&type=${encodeURIComponent(S.evFilter)}`}`);
    netOk();
    S.events = r.events; S.eventsErr = null;
  } catch (e) { S.eventsErr = e; netFail(e); if (S.events && e.code !== 'network') S.events = null; }
  renderActivity();
}
function searchKey() { return JSON.stringify([S.q.trim(), [...S.ignore].sort(), S.dateSel && [S.dateSel.from, S.dateSel.to], scoped()]); }
async function runSearch(force) {
  if (!needsSearch()) { S.search = { key: null, loading: false, res: null, err: null }; renderFiles(); return; }
  const key = searchKey();
  if (!force && S.search.key === key && (S.search.res || S.search.loading)) { renderFiles(); return; }
  const body = { query: S.q.trim(), limit: scoped() ? 100 : 10 };
  if (S.ignore.size) body.ignore = [...S.ignore];
  if (S.dateSel) { body.date_from = S.dateSel.from; body.date_to = S.dateSel.to; }
  S.search = { key, loading: true, res: S.search.key === key ? S.search.res : null, err: null };
  renderFiles();
  try {
    const res = await post('/api/search', body);
    netOk();
    if (S.search.key !== key) return;
    S.search = { key, loading: false, res, err: null };
    if (!S.ignore.size && !S.dateSel) S.parsedFor = { q: S.q, parsed: res.parsed };
    else if (!S.parsedFor || S.parsedFor.q !== S.q) S.parsedFor = { q: S.q, parsed: res.parsed };
  } catch (e) {
    netFail(e);
    if (S.search.key !== key) return;
    S.search = { key, loading: false, res: null, err: e };
  }
  renderFiles();
}
function submitSearch(q) {
  S.q = q;
  $('q').value = q;
  S.ignore.clear(); S.ignoredLabels = {}; S.parsedFor = null; S.sort = { k: null, dir: -1 };
  if (S.view !== 'files') { S.view = 'files'; mountView(); render(); }
  runSearch(true);
}

/* ---------- detail (F4) ---------- */
function selectFile(id, tab) {
  if (S.sel !== id) {
    S.sel = id; S.tok++;
    S.meta = S.byId.get(id) ? { ...S.byId.get(id) } : null;
    S.metaErr = null; S.hist = null; S.histErr = null; S.sum = null; S.selLoc = S.view === 'files' ? S.locById[id] ?? null : null;
  }
  if (tab) S.ptab = tab;
  renderPreview(); renderCmd(); renderFiles(); renderStatusBar();
  if (window.innerWidth <= 1180) { const c = document.querySelector('.p-close'); if (c) c.focus(); }
  loadDetail(true);
}
function closeDetail() {
  const id = S.sel;
  S.sel = null; S.tok++; S.meta = null;
  renderPreview(); renderCmd(); renderFiles(); renderStatusBar();
  const row = id && document.querySelector(`.trow[data-id="${id}"],.tile[data-id="${id}"]`);
  if (row) row.focus({ preventScroll: true });
}
async function loadDetail(first) {
  const id = S.sel, tok = S.tok;
  if (!id) return;
  const [m, h] = await Promise.allSettled([get(`/api/files/${id}`), get(`/api/files/${id}/history`)]);
  if (tok !== S.tok) return;
  if (m.status === 'fulfilled') { netOk(); S.meta = m.value; S.metaErr = null; }
  else if (m.reason.code === 'file_not_found') { closeDetail(); toast('That file is no longer in the index.', true); return; }
  else { netFail(m.reason); if (first || !S.meta) S.metaErr = m.reason; if (first) S.meta = null; }
  if (h.status === 'fulfilled') { S.hist = h.value.events; S.histErr = null; } else if (first || !S.hist) S.histErr = h.reason;
  renderPreview(); renderCmd(); renderStatusBar();
  if (first && S.meta) loadSummary(false);
}
async function loadSummary(force) {
  const id = S.sel, tok = S.tok;
  if (!id || !S.meta || S.meta.status !== 'indexed') { renderPreview(); return; }
  S.sum = { st: 'loading' };
  renderPreview();
  try {
    const r = await post(`/api/files/${id}/summary`, force ? { force: true } : {});
    if (tok !== S.tok) return;
    S.sum = { st: 'ready', ...r };
    if (!r.fallback && S.meta) S.meta.summary_cached = true;
  } catch (e) {
    netFail(e);
    if (tok !== S.tok) return;
    S.sum = { st: 'error', err: e };
  }
  renderPreview();
}

/* ---------- actions ---------- */
function openError(e) {
  return {
    file_missing: 'This file is gone from disk. Peekr queued a rescan of its folder.',
    forbidden_path: "This file is outside every indexed folder, so Peekr won't open it.",
    file_not_found: 'That file is no longer in the index.',
    os_error: `Windows couldn't open it: ${e.message}`,
  }[e.code] || errText(e);
}
async function openOs(kind) {
  const id = S.sel;
  if (!id) return;
  try {
    await post(`/api/files/${id}/${kind === 'file' ? 'open' : 'open-folder'}`);
    toast(kind === 'file' ? 'Opening in your default app…' : 'Opening the folder in Windows Explorer…');
  } catch (e) {
    netFail(e);
    toast(openError(e), true);
    if (e.code === 'file_missing') { pollIndex(); loadDetail(false); }
  }
}
async function startIndex(body, okMsg) {
  try { await post('/api/index/start', body); if (okMsg) toast(okMsg); return true; }
  catch (e) { netFail(e); toast(e.code === 'embedder_not_ready' ? `Indexing is blocked: ${e.message}` : errText(e), true); return false; }
  finally { pollIndex(); }
}
async function pickFolder() {
  S.picking = true; S.addErr = ''; renderFolders();
  try { const r = await post('/api/folders/pick'); if (r.path) S.addPath = r.path; }
  catch (e) { netFail(e); S.addErr = `${e.code}: ${e.message}`; }
  S.picking = false;
  renderFolders();
  const input = $('addpath');
  if (input && S.addPath) { input.value = S.addPath; input.focus(); }
}
async function addFolder() {
  const input = $('addpath'), path = (input ? input.value : S.addPath).trim();
  S.addPath = path;
  if (!path) { S.addErr = 'invalid_path: Enter a full folder path, or choose one with the dialog.'; renderFolders(); return; }
  S.adding = true; S.addErr = ''; renderFolders();
  try {
    const { folder } = await post('/api/folders', { path });
    S.addOpen = false; S.addPath = '';
    const started = await startIndex({ folder_id: folder.id, kind: 'initial' });
    toast(started ? 'Folder added. Indexing started.' : 'Folder added, but indexing could not start yet.', !started);
    await loadLibrary();
  } catch (e) { netFail(e); S.addErr = `${e.code}: ${e.message}`; }
  S.adding = false;
  renderCmd(); renderFolders();
}
async function removeFolder(id) {
  const fo = S.folders.find(f => f.id === id);
  S.busy = true; renderFolders();
  try {
    await del(`/api/folders/${id}`);
    S.removing = null;
    toast('Folder removed from Peekr. Your files are untouched.');
    if (fo && S.meta && inDir(S.meta.path, fo.path)) closeDetail();
    if (fo && S.scope.folder && (normP(S.scope.folder) === normP(fo.path) || inDir(S.scope.folder, fo.path))) S.scope.folder = null;
    await loadLibrary();
  } catch (e) { netFail(e); toast(e.code === 'folder_not_found' ? 'That folder was already removed.' : errText(e), true); if (e.code === 'folder_not_found') loadLibrary(); }
  S.busy = false;
  renderFolders();
}
async function addExclusion(id) {
  const input = $(`exclpath-${id}`), path = input ? input.value.trim() : '';
  if (!path) { S.exclErr = 'Enter a subfolder name or a full path inside this folder.'; renderFolders(); return; }
  S.busy = true; S.exclErr = ''; renderFolders();
  try {
    await post(`/api/folders/${id}/exclusions`, { path });
    S.exclOpen = null;
    toast("Excluded. Peekr won't read that subfolder.");
    pollIndex();
    await loadLibrary();
  } catch (e) { netFail(e); S.exclErr = e.message; }
  S.busy = false;
  renderFolders();
}
function closeMenus(focusBtn) {
  const was = S.dateOpen ? 'date-toggle' : S.themeOpen ? 'theme-toggle' : null;
  if (!was) return false;
  S.dateOpen = false; S.themeOpen = false;
  renderDate(); renderTheme();
  if (focusBtn) { const b = document.querySelector(`[data-act="${was}"]`); if (b) b.focus(); }
  return true;
}
function openMenu(which) {
  S.dateOpen = which === 'date' ? !S.dateOpen : false;
  S.themeOpen = which === 'theme' ? !S.themeOpen : false;
  renderDate(); renderTheme();
  const menu = document.querySelector('.datemenu');
  if (menu) (menu.querySelector('[aria-checked="true"]') || menu.querySelector('button')).focus();
}
function pickDate(label, from, to) {
  S.dateSel = { label, from: from.toISOString(), to: to.toISOString() };
  S.dateOpen = false;
  S.ignore.delete('date'); delete S.ignoredLabels.date;
  if (S.view !== 'files') { S.view = 'files'; mountView(); }
  render();
  runSearch(true);
}

document.addEventListener('click', e => {
  if (e.target.id === 'scrim') { closeDetail(); return; }
  if ((S.dateOpen || S.themeOpen) && !e.target.closest('.datewrap')) closeMenus(false);
  const b = e.target.closest('[data-act]');
  if (!b || b.disabled) return;
  const a = b.dataset.act, id = Number(b.dataset.id) || null;
  switch (a) {
    case 'nav': setView(b.dataset.v); break;
    case 'crumb': { const fn = crumbFns[Number(b.dataset.i)]; if (fn) fn(); break; }
    case 'scope-all': setScope(null, null); break;
    case 'scope-cat': setScope(null, b.dataset.c); break;
    case 'scope-folder': setScope(b.dataset.p, null); break;
    case 'tree-toggle': e.stopPropagation(); S.collapsed[b.dataset.p] = !S.collapsed[b.dataset.p]; renderNav(); break;
    case 'unscope': setScope(b.dataset.k === 'cat' ? S.scope.folder : null, b.dataset.k === 'cat' ? null : S.scope.cat); break;
    case 'clearq': submitSearch(''); break;
    case 'ex': submitSearch(b.dataset.l); break;
    case 'chip': {
      const k = b.dataset.k;
      if (k === 'date' && S.dateSel) { S.dateSel = null; renderDate(); }
      else if (S.ignore.has(k)) { S.ignore.delete(k); delete S.ignoredLabels[k]; }
      else { S.ignore.add(k); S.ignoredLabels[k] = b.dataset.l; }
      runSearch(true);
      break;
    }
    case 'date-toggle': openMenu('date'); break;
    case 'theme-toggle': openMenu('theme'); break;
    case 'theme-pick': window.PeekrTheme.set(b.dataset.k); closeMenus(true); break;
    case 'date-clear': S.dateSel = null; S.dateOpen = false; renderDate(); runSearch(true); break;
    case 'date-pick': { const p = presets().find(x => x[0] === b.dataset.l); if (p) pickDate(p[0], p[1], p[2]); break; }
    case 'date-custom': {
      const f = $('dfrom').value, t = $('dto').value;
      if (!f || !t || f > t) { toast('Choose a start date that is on or before the end date.', true); break; }
      S.dFrom = f; S.dTo = t;
      const [fy, fm, fdd] = f.split('-').map(Number), [ty, tm, tdd] = t.split('-').map(Number);
      const from = new Date(fy, fm - 1, fdd), to = new Date(ty, tm - 1, tdd + 1);
      pickDate(dateLabel(from.toISOString(), to.toISOString()), from, to);
      break;
    }
    case 'sort': { const k = b.dataset.k; if (S.sort.k === k) S.sort.dir *= -1; else S.sort = { k, dir: ['name', 'loc', 'cat'].includes(k) ? 1 : -1 }; renderFiles(); break; }
    case 'mode': S.mode = b.dataset.m; if (store) store.setItem('peekr-mode', S.mode); renderCmd(); renderFiles(); break;
    case 'select': if (id) selectFile(id); break;
    case 'select-hist': if (id) { if (S.view !== 'activity') setView('activity'); selectFile(id, 'history'); } break;
    case 'ptab': S.ptab = b.dataset.t; renderPreview(); break;
    case 'close-detail': closeDetail(); break;
    case 'regen': loadSummary(true); break;
    case 'open-os': openOs('file'); break;
    case 'open-folder': openOs('folder'); break;
    case 'ollama-retry': {
      const was = S.health && S.health.ollama_ok && S.health.llm_ready;
      loadHealth().then(() => { if (!was && aiOk()) toast('Ollama is back. Summaries use the local model again.'); else if (!aiOk()) toast('Still not reachable. Peekr checks again every few seconds.', true); });
      break;
    }
    case 'retry-all': loadAll(); break;
    case 'retry-search': runSearch(true); break;
    case 'retry-detail': loadDetail(true); break;
    case 'retry-events': S.eventsErr = null; renderActivity(); loadEvents(); break;
    case 'add-open': S.addOpen = true; S.addErr = ''; setView('folders'); { const i = $('addpath'); if (i) i.focus(); } break;
    case 'add-toggle': S.addOpen = !S.addOpen; S.addErr = ''; renderCmd(); renderFolders(); { const i = $('addpath'); if (i) i.focus(); } break;
    case 'pick': pickFolder(); break;
    case 'add': addFolder(); break;
    case 'rescan': if (!jobActive()) startIndex(id ? { folder_id: id, kind: 'rescan' } : { kind: 'rescan' }, 'Rescan started.'); break;
    case 'remove': S.removing = id; renderFolders(); break;
    case 'remove-no': S.removing = null; renderFolders(); break;
    case 'remove-yes': removeFolder(id); break;
    case 'excl-toggle': S.exclOpen = S.exclOpen === id ? null : id; S.exclErr = ''; renderFolders(); { const i = $(`exclpath-${id}`); if (i) i.focus(); } break;
    case 'excl-save': addExclusion(id); break;
    case 'evf': S.evFilter = b.dataset.k; S.events = null; renderActivity(); loadEvents(); break;
  }
});
document.addEventListener('dblclick', e => {
  const r = e.target.closest('.trow,.tile');
  if (r && Number(r.dataset.id) === S.sel && S.meta && S.meta.status !== 'deleted') openOs('file');
});
$('sform').addEventListener('submit', e => { e.preventDefault(); submitSearch($('q').value); });
document.addEventListener('input', e => { if (e.target.id === 'addpath') S.addPath = e.target.value; });
document.addEventListener('keydown', e => {
  const t = e.target, typing = t && (t.tagName === 'INPUT' || t.tagName === 'SELECT' || t.tagName === 'TEXTAREA');
  if (e.key === 'Escape') {
    if (closeMenus(true)) return;
    if (S.sel) { closeDetail(); return; }
  }
  if (e.key === 'Enter' && t.id === 'addpath') { e.preventDefault(); addFolder(); return; }
  if (e.key === 'Enter' && t.id && t.id.startsWith('exclpath-')) { e.preventDefault(); addExclusion(Number(t.id.slice(9))); return; }
  if (S.view === 'files' && !typing && (e.key === 'ArrowDown' || e.key === 'ArrowUp') && S.order.length && (t === document.body || t.closest('#view'))) {
    e.preventDefault();
    const i = S.order.indexOf(S.sel);
    const n = e.key === 'ArrowDown' ? Math.min(S.order.length - 1, i + 1) : Math.max(0, i < 0 ? 0 : i - 1);
    selectFile(S.order[n]);
    const row = document.querySelector(`.trow[data-id="${S.order[n]}"],.tile[data-id="${S.order[n]}"]`);
    if (row) { row.focus({ preventScroll: true }); row.scrollIntoView({ block: 'nearest' }); }
  }
  if (e.key === 'Enter' && !typing && t.classList && t.classList.contains('trow')) selectFile(Number(t.dataset.id));
});
document.addEventListener('peekr:theme', renderTheme);

/* ---------- polling and boot ---------- */
function every(ms, fn) {
  let busy = false;
  const tick = async () => {
    if (busy || document.hidden) return;
    busy = true;
    try { await fn(); } catch (err) { console.error(err); } finally { busy = false; }
  };
  setInterval(tick, ms);
  return tick;
}
const ticks = [
  every(1000, pollIndex),
  every(5000, loadHealth),
  every(5000, async () => { await loadLibrary(); if (S.view === 'activity') await loadEvents(); }),
  every(3000, async () => { if (S.sel) await loadDetail(false); }),
];
document.addEventListener('visibilitychange', () => { if (!document.hidden) ticks.forEach(t => t()); });
setInterval(() => { if (S.view === 'folders') renderFolders(); }, 60000); // keep "last scan N min ago" fresh

$('sic').innerHTML = ic('search');
mountView();
render();
loadAll();
