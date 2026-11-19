'use strict';
/* ==========================================================================
   AI TZ Generatoru: UI məntiqi (Vanilla JS). Backend: FastAPI (API müqaviləsi README-də).
   XSS: istifadəçi/AI mətni həmişə textContent ilə yazılır; markdown yalnız əvvəlcədən escape olunmuş mətndən qurulur.
   ========================================================================== */

/* ---------- 1. API qatı (bütün sorğular bir yerdə) ---------- */
class ApiError extends Error {
  constructor(kind, status, detail) {
    super(kind);
    this.kind = kind;       // network | session | rate | llm | validation | not_ready | pdf | server
    this.status = status;
    this.detail = detail || {};
  }
}

const KIND_BY_STATUS = { 404: 'session', 429: 'rate', 503: 'llm', 422: 'validation', 501: 'pdf' };

async function request(method, path, body) {
  let res;
  try {
    res = await fetch(path, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new ApiError('network', 0);
  }
  if (res.ok) return res;
  let detail = {};
  try { detail = (await res.json()).detail || {}; } catch (e) { /* gövdə JSON deyil */ }
  let kind = KIND_BY_STATUS[res.status] || 'server';
  if (res.status === 409 && detail.code === 'not_ready') kind = 'not_ready';
  throw new ApiError(kind, res.status, detail);
}

const json = async (p) => (await p).json();

const api = {
  createSession: (language) => json(request('POST', '/sessions', { consent: true, language })),
  sendMessage: (id, text) => json(request('POST', `/sessions/${id}/messages`, { text })),
  getState: (id) => json(request('GET', `/sessions/${id}/state`)),
  getSummary: (id) => json(request('GET', `/sessions/${id}/summary`)),
  editAnswers: (id, body) => json(request('POST', `/sessions/${id}/answers`, body)),
  pageOps: (id, ops) => json(request('POST', `/sessions/${id}/page-ops`, { ops })),
  uploadFiles: (id, files) => json(request('POST', `/sessions/${id}/files`, { files })),
  deleteFile: (id, fid) => json(request('DELETE', `/sessions/${id}/files/${fid}`)),
  confirm: (id) => json(request('POST', `/sessions/${id}/confirm`)),
  deleteSession: (id) => json(request('DELETE', `/sessions/${id}`)),
  sendFeedback: (id, rating, comment) => json(request('POST', `/sessions/${id}/feedback`, { rating, comment })),
  async download(id, format) {
    const res = await request('GET', `/sessions/${id}/download?format=${format}`);
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = format === 'assets' ? 'Texniki_Tapsiriq_files.zip' : `Texniki_Tapsiriq.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  },
};

/* ---------- 2. Sessiya ID-si (localStorage, try/catch ilə) ---------- */
const SESSION_KEY = 'ai_tz_session_id';
const store = {
  get() { try { return localStorage.getItem(SESSION_KEY); } catch (e) { return null; } },
  set(v) { try { localStorage.setItem(SESSION_KEY, v); } catch (e) { /* private rejim */ } },
  clear() { try { localStorage.removeItem(SESSION_KEY); } catch (e) { /* ignore */ } },
};

/* ---------- 3. Vəziyyət və DOM ---------- */
const State = { sessionId: null, screen: 'welcome', busy: false, rating: 5, summary: null, notice: null };
const $ = (id) => document.getElementById(id);
const el = {
  consent: $('consent-checkbox'), startBtn: $('start-btn'), restoreBtn: $('restore-session-btn'),
  resetBtn: $('reset-session-header-btn'), chatMessages: $('chat-messages'), chatInput: $('chat-input'),
  sendBtn: $('send-btn'), typing: $('typing-indicator'), progressBar: $('progress-bar'),
  progressText: $('progress-text'), sections: $('sections-container'), charCounter: $('char-counter'),
  errorBanner: $('error-banner'), errorText: $('error-message-text'), retryBtn: $('retry-action-btn'),
  editBtn: $('edit-btn'), confirmBtn: $('confirm-btn'), docx: $('download-docx'), pdf: $('download-pdf'),
  deleteBtn: $('delete-data-btn'), deleteModal: $('delete-modal'), modalCancel: $('modal-cancel-btn'),
  modalDelete: $('modal-confirm-delete-btn'), viewSummary: $('view-summary-btn'),
  finishChat: $('finish-chat-direct-btn'), stars: $('star-rating-box'), sendFeedback: $('send-feedback-btn'),
};

/** Təhlükəsiz DOM yaradıcı: uşaqlar string-dirsə textContent kimi yazılır. */
function h(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    if (k === 'class') n.className = v;
    else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    n.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return n;
}

function icon(cls) { return h('i', { class: cls }); }

function navigateTo(name) {
  document.querySelectorAll('.screen-view').forEach((s) => s.classList.add('hidden'));
  const t = document.querySelector(`[data-screen="${name}"]`);
  if (t) { t.classList.remove('hidden'); State.screen = name; window.scrollTo({ top: 0 }); }
}

/* ---------- 4. Xəta banneri ---------- */
function showError(message, onRetry, retryLabel = T('Yenidən cəhd et')) {
  el.errorText.textContent = message;
  el.errorBanner.classList.remove('hidden');
  el.retryBtn.textContent = retryLabel;
  el.retryBtn.classList.toggle('hidden', !onRetry);
  el.retryBtn.onclick = onRetry ? () => { hideError(); onRetry(); } : null;
}
function hideError() { el.errorBanner.classList.add('hidden'); }

/** ApiError → müştəri dilində mesaj + düzgün hərəkət. */
function handleApiError(err, retry) {
  const kind = err && err.kind;
  if (kind === 'network') return showError(T('İnternet bağlantısı kəsilib. Bağlantını yoxlayıb yenidən cəhd edin.'), retry);
  if (kind === 'llm') return showError(T('AI köməkçi hazırda cavab vermir. Bir az sonra yenidən cəhd edin.'), retry);
  if (kind === 'rate') {
    const s = err.detail.retry_after || 30;
    return showError(T('Çox tez-tez mesaj göndərdiniz. {s} saniyə gözləyib yenidən cəhd edin.', { s }), retry);
  }
  if (kind === 'session') return showError(T('Sessiyanın vaxtı keçib və ya silinib. Yeni söhbətə başlaya bilərsiniz.'), resetLocal, T('Yeni başla'));
  if (kind === 'validation') return showError(T('Mesaj çox uzundur və ya boşdur (maksimum 2000 simvol).'));
  if (kind === 'pdf') return showError(T('PDF hazırda yaradıla bilmir. DOCX formatını yükləyə bilərsiniz.'));
  if (kind === 'not_ready') {
    return showError(T('TZ hələ tam deyil: {list}', { list: (err.detail.missing || []).join(', ') }), () => navigateTo('chat'), T('Söhbətə qayıt'));
  }
  return showError(T('Gözlənilməz xəta baş verdi. Yenidən cəhd edin.'), retry);
}

function resetLocal() { store.clear(); location.reload(); }

/* ---------- 5. Təhlükəsiz markdown (əvvəlcə escape, sonra yalnız **qalın** və siyahı) ---------- */
function escapeHTML(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function renderMarkdown(text) {
  return escapeHTML(text).split(/\n{2,}/).map((block) => {
    const lines = block.split('\n');
    const inline = (s) => s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    if (lines.every((l) => l.startsWith('- '))) {
      return '<ul>' + lines.map((l) => `<li>${inline(l.slice(2))}</li>`).join('') + '</ul>';
    }
    return '<p>' + lines.map(inline).join('<br>') + '</p>';
  }).join('');
}

/* ---------- 6. Söhbət ---------- */
const nowTime = () => new Date().toTimeString().slice(0, 5);
const scrollBottom = () => { el.chatMessages.scrollTop = el.chatMessages.scrollHeight; };

function appendUserMessage(text, time) {
  const n = $('tmpl-user-message').content.cloneNode(true);
  const bubble = n.querySelector('.msg-bubble');
  bubble.textContent = text;                       // XSS: textContent
  n.querySelector('.msg-time').textContent = time || nowTime();
  el.chatMessages.appendChild(n);
  scrollBottom();
  return el.chatMessages.lastElementChild.querySelector('.msg-bubble');
}

function appendAiMessage({ reply, chips = [], show_tree = false, widget = null, why = '', time }, { live = true } = {}) {
  if (live) {  // köhnə chips və səhifə ağacı kartlarını təmizlə: yalnız ən sonuncu aktivdir
    el.chatMessages.querySelectorAll('.chips-container').forEach((c) => c.replaceChildren());
    el.chatMessages.querySelectorAll('.why-line').forEach((w) => w.remove());  // «niyə soruşuruq» yalnız aktiv sualda qalır
  }
  const n = $('tmpl-ai-message').content.cloneNode(true);
  const bubble = n.querySelector('.msg-bubble');
  bubble.innerHTML = renderMarkdown(reply);        // əvvəlcə escape olunub
  if (why) {  // «niyə soruşuruq»: qısa izah, textContent ilə
    bubble.appendChild(h('p', { class: 'why-line' }, icon('fa-regular fa-circle-question'), ' ', T('Niyə soruşuruq: {text}', { text: why })));
  }
  n.querySelector('.msg-time').textContent = time || nowTime();
  const box = n.querySelector('.chips-container');
  chips.forEach((c) => box.appendChild(h('button', { class: 'chip-btn', type: 'button', onclick: () => onChip(c) }, c)));
  if (show_tree) {
    el.chatMessages.querySelectorAll('.page-tree-card').forEach((t) => t.remove());
    bubble.appendChild(buildTreeCard());
  }
  if (widget) {
    el.chatMessages.querySelectorAll('.chat-widget').forEach((w) => w.remove());  // yalnız ən son sual aktivdir
    const w = buildWidget(widget);
    if (w) box.before(w);
  }
  el.chatMessages.appendChild(n);
  scrollBottom();
}

/* Söhbət daxilində loqo yükləmə düyməsi və rəng seçici */
function buildWidget(kind) {
  if (kind === 'logo') {
    return h('div', { class: 'chat-widget' },
      h('button', { class: 'widget-btn', type: 'button', onclick: () => pickFiles('logo') },
        icon('fa-solid fa-upload'), ' ', T('Loqo yüklə')),
      h('button', { class: 'widget-btn ghost', type: 'button', onclick: () => pickFiles('guide') },
        icon('fa-solid fa-file-pdf'), ' ', T('Brend bələdçisi (PDF)')),
      h('span', { class: 'widget-hint' }, T('Bir neçə fayl seçə bilərsiniz. PNG / JPG / PDF, hər biri maks. 2 MB')));
  }
  if (kind === 'references') {
    return h('div', { class: 'chat-widget' },
      h('button', { class: 'widget-btn', type: 'button', onclick: () => pickFiles('reference') },
        icon('fa-solid fa-images'), ' ', T('Skrinşot yüklə')),
      h('span', { class: 'widget-hint' }, T('Bir neçə şəkil seçə bilərsiniz. PNG / JPG, hər biri maks. 2 MB')));
  }
  if (kind === 'colors') {
    const pickers = [];  // yalnız istifadəçinin toxunduğu rənglər göndərilir (susmaya görə rəng uydurulmur)
    const row = h('div', { class: 'color-row' });
    const sendBtn = h('button', { class: 'widget-btn', type: 'button', disabled: true, onclick: () => {
      sendText(pickers.filter((p) => p.touched).map((p) => p.input.value.toUpperCase()).join(', '));
    } }, icon('fa-solid fa-paper-plane'), ' ', T('Rəngləri göndər'));
    const addBtn = h('button', { class: 'widget-btn ghost', type: 'button', onclick: () => addPicker() }, '+ ', T('Rəng əlavə et'));
    function addPicker() {
      const input = h('input', { type: 'color', value: '#0a3d91', class: 'color-input', 'aria-label': T('Rəng seç') });
      const p = { input, touched: false };
      input.addEventListener('input', () => { p.touched = true; sendBtn.disabled = false; });
      pickers.push(p);
      row.appendChild(input);
      addBtn.hidden = pickers.length >= 3;
    }
    addPicker();
    return h('div', { class: 'chat-widget' }, row, addBtn, sendBtn);
  }
  return null;
}

const SUMMARY_CHIPS = ['Xülasəyə bax', 'View summary', 'Посмотреть сводку'];
function onChip(text) {
  if (SUMMARY_CHIPS.includes(text)) return openSummary();
  sendText(text);
}

function applyTurn(res) {
  applyState(res.state);
  appendAiMessage(res);
}

function setBusy(b) {
  State.busy = b;
  el.sendBtn.disabled = b;
  el.typing.classList.toggle('hidden', !b);
  if (b) scrollBottom();
}

async function sendText(text, existingBubble = null) {
  text = text.trim();
  if (!text || State.busy) return;
  hideError();
  const bubble = existingBubble || appendUserMessage(text);
  bubble.classList.remove('msg-failed');
  setBusy(true);
  try {
    applyTurn(await api.sendMessage(State.sessionId, text));
  } catch (err) {
    bubble.classList.add('msg-failed');
    handleApiError(err, () => sendText(text, bubble));
  } finally {
    setBusy(false);
  }
}

function sendFromInput() {
  const text = el.chatInput.value.trim();
  if (!text || State.busy) return;
  el.chatInput.value = '';
  el.chatInput.style.height = 'auto';
  updateCounter();
  sendText(text);
}

function updateCounter() {
  const n = el.chatInput.value.length;
  el.charCounter.textContent = `${n} / 2000`;
  el.charCounter.classList.toggle('warning', n > 1800);
}

/* ---------- 7. Səhifə ağacı kartı (prompt() yoxdur: redaktə kartın içindədir) ---------- */
let pageTree = [];
let editingId = null;   // redaktə olunan səhifənin id-si

const txtInput = (ph, val = '', max = '80') => h('input', { type: 'text', class: 'tree-input', maxlength: max, placeholder: ph, value: val, 'aria-label': ph });
const rerenderTrees = () => document.querySelectorAll('[data-tree]').forEach(renderTree);

function buildTreeCard() {
  const card = $('tmpl-page-tree').content.cloneNode(true);
  const root = card.querySelector('.page-tree-card');
  const list = card.querySelector('#tree-list-dynamic');
  list.removeAttribute('id');
  list.dataset.tree = '1';
  renderTree(list);

  // yeni səhifə: ad + qısa təsvir
  const add = card.querySelector('#add-tree-page-btn');
  add.removeAttribute('id');
  add.type = 'button';
  const nameIn = txtInput(T('Səhifənin adı'));
  const purposeIn = txtInput(T('Qısa təsvir (ixtiyari)'), '', '300');
  const submitAdd = () => {
    const name = nameIn.value.trim();
    if (!name) return nameIn.focus();
    runPageOps([{ op: 'add', name, purpose: purposeIn.value.trim() || null }]);
  };
  const addForm = h('div', { class: 'tree-edit hidden' }, nameIn, purposeIn,
    h('div', { class: 'tree-edit-actions' },
      h('button', { type: 'button', class: 'btn btn-primary btn-sm', onclick: submitAdd }, T('Əlavə et')),
      h('button', { type: 'button', class: 'btn btn-secondary btn-sm', onclick: () => addForm.classList.add('hidden') }, T('Ləğv et'))));
  [nameIn, purposeIn].forEach((i) => i.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); submitAdd(); } }));
  add.addEventListener('click', () => { addForm.classList.toggle('hidden'); if (!addForm.classList.contains('hidden')) nameIn.focus(); });
  add.after(addForm);

  // sərbəst mətn: "bunu əlavə et / dəyiş" (adi mesaj kimi göndərilir)
  const freeIn = h('input', { type: 'text', class: 'tree-input', maxlength: '2000', 'aria-label': T('Nə əlavə etmək və ya dəyişmək istəyirsiniz? Özünüz yazın...'), placeholder: T('Nə əlavə etmək və ya dəyişmək istəyirsiniz? Özünüz yazın...') });
  const free = h('form', { class: 'tree-free' }, freeIn, h('button', { type: 'submit', class: 'btn btn-primary btn-sm' }, T('Göndər')));
  free.addEventListener('submit', (e) => {
    e.preventDefault();
    const v = freeIn.value.trim();
    if (v) { freeIn.value = ''; sendText(v); }
  });
  root.appendChild(free);
  return card;
}

/** Səhifənin məzmunu (müştərinin dediyi) və ya «dəqiqləşdirilməyib» qeydi. */
function pageContentLine(p) {
  if (p.content) return h('span', { class: 'tree-modules' }, T('Məzmun: {text}', { text: p.content }));
  if (p.content_status === 'open') return h('span', { class: 'tree-modules' }, T('Məzmun: dəqiqləşdirilməyib'));
  return null;
}

function renderTree(list) {
  list.replaceChildren(...pageTree.map((p) => {
    if (p.id === editingId) {
      const nIn = txtInput(T('Səhifənin adı'), p.name);
      const pIn = txtInput(T('Qısa təsvir (ixtiyari)'), p.purpose || '', '300');
      const save = () => {
        const nn = nIn.value.trim();
        if (!nn) return nIn.focus();
        editingId = null;
        runPageOps([{ op: 'rename', name: p.name, new_name: nn, purpose: pIn.value.trim() }]);
      };
      [nIn, pIn].forEach((i) => i.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); save(); } }));
      return h('li', { class: 'tree-item editing' }, h('div', { class: 'tree-edit' }, nIn, pIn,
        h('div', { class: 'tree-edit-actions' },
          h('button', { type: 'button', class: 'btn btn-primary btn-sm', onclick: save }, T('Saxla')),
          h('button', { type: 'button', class: 'btn btn-secondary btn-sm', onclick: () => { editingId = null; rerenderTrees(); } }, T('Ləğv et')))));
    }
    return h('li', { class: 'tree-item' },
      h('div', { class: 'tree-item-text' },
        h('span', { class: 'tree-item-title' }, icon('fa-solid fa-file'), p.name,
          p.kind === 'custom' ? h('span', { class: 'tree-badge' }, T('xüsusi')) : null),
        p.purpose ? h('span', { class: 'tree-modules' }, p.purpose) : null,
        pageContentLine(p),
        p.modules.length ? h('span', { class: 'tree-modules' }, p.modules.map((m) => m.title).join(' · ')) : null),
      h('div', { class: 'tree-actions' },
        h('button', { class: 'tree-btn', type: 'button', title: T('Dəyiş'), 'aria-label': T('Dəyiş'),
          onclick: () => { editingId = p.id; rerenderTrees(); } }, icon('fa-solid fa-pen')),
        h('button', { class: 'tree-btn delete', type: 'button', title: T('Sil'), 'aria-label': T('Sil'),
          onclick: () => runPageOps([{ op: 'remove', name: p.name }]) }, icon('fa-solid fa-trash'))));
  }));
}

async function runPageOps(ops) {
  if (State.busy) return;
  hideError();
  setBusy(true);
  try {
    applyTurn(await api.pageOps(State.sessionId, ops));
  } catch (err) {
    handleApiError(err, () => runPageOps(ops));
  } finally {
    setBusy(false);
  }
}

/* ---------- 8. İrəliləyiş paneli ---------- */
const STATUS_TEXT = { completed: 'Tamamlandı', in_progress: 'Davam edir', pending: 'Gözləyir' };
const SOURCE_TEXT = { user: 'Siz dediniz', inferred: 'Təxmin edildi (təsdiq lazımdır)', template: 'Şablondan',
  calculated: 'Hesablanıb', open: 'Dəqiqləşdirilməlidir' };
const sourceTag = (src) => (SOURCE_TEXT[src] ? h('span', { class: `source-tag ${src}` }, T(SOURCE_TEXT[src])) : null);
const expanded = new Set();

function applyState(st) {
  if (!st) return;
  pageTree = st.page_tree || [];
  el.progressBar.style.width = `${st.progress}%`;
  el.progressText.textContent = `${st.progress}%`;
  renderSections(st.sections || []);
  document.querySelectorAll('[data-tree]').forEach(renderTree);
}

function renderSections(sections) {
  el.sections.replaceChildren(...sections.map((s) => {
    const open = expanded.has(s.id);
    const details = open ? h('div', { class: 'section-details' },
      s.items.filter((i) => !i.req).slice(0, 10).map((i) => h('div', {}, h('strong', {}, i.label + ': '), String(i.value))),
      s.items.some((i) => i.req) ? h('div', { class: 'muted' }, T('+ {n} standart tələb', { n: s.items.filter((i) => i.req).length })) : null) : null;
    return h('div', { class: 'section-nav-item' + (open ? ' active' : ''), 'data-section': s.id,
      onclick: () => { open ? expanded.delete(s.id) : expanded.add(s.id); renderSections(sections); } },
      h('div', { class: 'sec-header' },
        h('span', { class: 'sec-title' }, s.title),
        h('span', { class: `status-badge ${s.status}` }, T(STATUS_TEXT[s.status]))),
      h('div', { class: 'sec-snippet' }, s.snippet),
      sourceTag(s.source),
      details);
  }));
}

/* ---------- 9. Xülasə ekranı ---------- */
async function openSummary() {
  hideError();
  try {
    State.summary = await api.getSummary(State.sessionId);
    renderSummary(State.summary);
    navigateTo('summary');
  } catch (err) {
    handleApiError(err, openSummary);
  }
}

/* ---------- 9b. Xülasədə cavabı düzəltmək (söhbətə qayıtmadan) ---------- */
let editingKey = null;   // 'f:<sahə id>' və ya 'p:<səhifə id>': eyni anda yalnız bir redaktor açıqdır
const OTHER_CHOICE = '__other__';

function editBtn(key) {
  return h('button', { class: 'tree-btn inline-edit', type: 'button', title: T('Dəyiş'), 'aria-label': T('Dəyiş'),
    onclick: () => { editingKey = key; State.notice = null; renderSummary(State.summary); } }, icon('fa-solid fa-pen'));
}

function summaryNotice() {
  const n = State.notice;
  if (!n) return null;
  return h('div', { class: 'edit-notice ' + n.kind },
    h('span', {}, n.text),
    n.kind === 'chat' ? h('button', { class: 'btn btn-secondary btn-sm', type: 'button',
      onclick: () => { State.notice = null; restoreSession(); } }, T('Söhbətə qayıt')) : null);
}

async function saveAnswers(body) {
  hideError();
  try {
    const res = await api.editAnswers(State.sessionId, body);
    State.summary = res.summary;
    editingKey = null;
    const parts = [res.needs_chat ? T('Bu düzəlişə görə yeni suallar əlavə olundu. Söhbətdə cavablandıra bilərsiniz.') : T('Dəyişiklik yadda saxlanıldı.')];
    if (res.dropped && res.dropped.length) parts.push(T('Artıq lazım olmayan məlumat silindi: {list}.', { list: res.dropped.join(', ') }));
    if (res.rejected && res.rejected.length) parts.push(T('Qəbul olunmadı: {list}.', { list: res.rejected.join(', ') }));
    State.notice = { kind: res.needs_chat ? 'chat' : 'ok', text: parts.join(' ') };
    applyState(res.state);
    renderSummary(State.summary);
  } catch (err) {
    if (err.status === 422 && err.detail && err.detail.code === 'invalid_value') {
      return showError(T('Cavab qəbul olunmadı. Dəyəri yoxlayıb yenidən yazın.'));
    }
    handleApiError(err, () => saveAnswers(body));
  }
}

function cancelEdit() { editingKey = null; renderSummary(State.summary); }

function editorActions(onSave, extra) {
  return h('div', { class: 'tree-edit-actions' },
    h('button', { type: 'button', class: 'btn btn-primary btn-sm', onclick: onSave }, T('Saxla')),
    h('button', { type: 'button', class: 'btn btn-secondary btn-sm', onclick: cancelEdit }, T('Ləğv et')),
    extra);
}

/** Bir sahənin redaktoru: seçim → siyahı (+ «digər»), mətn/e-poçt → xana. Server dəyəri söhbətdəki kimi yoxlayır. */
function fieldEditor(i) {
  const cur = i.source === 'open' ? '' : String(i.value);
  const choices = Array.isArray(i.options) && i.options.length ? i.options : null;
  let sel = null;
  const long = !choices && (i.input === 'text');
  const input = long
    ? h('textarea', { class: 'edit-input', rows: '3', maxlength: '500', 'aria-label': i.label })
    : h('input', { type: i.input === 'email' ? 'email' : 'text', class: 'edit-input', maxlength: '200', 'aria-label': i.label });
  if (choices) {
    sel = h('select', { class: 'edit-input', 'aria-label': i.label },
      choices.map((o) => h('option', { value: o }, o)), h('option', { value: OTHER_CHOICE }, T('Digər (yazın)...')));
    sel.value = choices.includes(cur) ? cur : (cur ? OTHER_CHOICE : choices[0]);
    input.value = choices.includes(cur) ? '' : cur;
    const sync = () => input.classList.toggle('hidden', sel.value !== OTHER_CHOICE);
    sel.addEventListener('change', sync);
    sync();
  } else {
    input.value = cur;
  }
  const save = () => {
    const v = sel && sel.value !== OTHER_CHOICE ? sel.value : input.value.trim();
    if (!v) return input.focus();
    saveAnswers({ fields: { [i.field_id]: v } });
  };
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') cancelEdit();
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); save(); }
  });
  const later = i.skippable === false ? null : h('button', { type: 'button', class: 'btn btn-secondary btn-sm',
    onclick: () => saveAnswers({ open: [i.field_id] }) }, T('Developer ilə dəqiqləşdirəcəm'));
  const box = h('div', { class: 'inline-editor' }, h('strong', {}, i.label), sel, input, editorActions(save, later));
  setTimeout(() => (sel || input).focus(), 0);
  return box;
}

function editableView(i, view) {
  if (!i.editable || !i.field_id) return view;
  if (editingKey === 'f:' + i.field_id) return fieldEditor(i);
  view.append(editBtn('f:' + i.field_id));
  return view;
}
const shortRow = (i) => editableView(i, kv(i.label, i.value, i.swatches));
const longRow = (i) => editableView(i, h('li', {}, i.req ? String(i.value) : `${i.label}: ${i.value}`));

function summaryPageContent(p) {
  if (editingKey === 'p:' + p.id) {
    const ta = h('textarea', { class: 'edit-input', rows: '3', maxlength: '800', 'aria-label': T('Səhifənin məzmunu') });
    ta.value = p.content || '';
    ta.addEventListener('keydown', (e) => { if (e.key === 'Escape') cancelEdit(); });
    setTimeout(() => ta.focus(), 0);
    return h('div', { class: 'inline-editor' }, h('strong', {}, `${p.name}: ${T('Səhifənin məzmunu')}`), ta,
      editorActions(() => saveAnswers({ page_content: { [p.id]: ta.value.trim() } })));
  }
  const line = pageContentLine(p);
  return h('span', { class: 'page-content-row' }, line || h('span', { class: 'tree-modules' }, T('Məzmun: dəqiqləşdirilməyib')), editBtn('p:' + p.id));
}

const HEX6 = /^#[0-9A-Fa-f]{6}$/;
/** Rəng nümunələri: yalnız #RRGGBB (server də yoxlayır, burada style-a yazmazdan əvvəl bir daha). */
function swatchRow(colors) {
  return h('span', { class: 'swatch-row' }, colors.filter((c) => HEX6.test(c)).map((c) =>
    h('span', { class: 'swatch' }, h('i', { class: 'swatch-dot', style: `background:${c}` }), c)));
}
function kv(label, value, swatches) {
  return h('p', { class: 'kv' }, h('strong', {}, label + ': '), String(value), swatches && swatches.length ? swatchRow(swatches) : null);
}

function renderSummary(tz) {
  const warns = $('summary-warnings');
  warns.replaceChildren(...[summaryNotice(), ...(tz.warnings.length ? [h('div', { class: 'warn-box' },
    h('strong', {}, T('⚠️ Diqqət')), h('ul', {}, tz.warnings.map((w) => h('li', {}, w))))] : [])].filter(Boolean));

  const cb = $('clarification-box');
  cb.classList.toggle('hidden', tz.clarifications.length === 0);
  $('clarification-list').replaceChildren(...tz.clarifications.map((c) => h('li', {}, c)));

  $('summary-cards-container').replaceChildren(...tz.sections.map((s) => {
    const inferred = s.items.some((i) => i.source === 'inferred' || i.source === 'open');
    const long = [5, 6, 7].includes(s.number);
    let body;
    if (s.number === 3) {
      body = h('ul', { class: 'tree-list' }, tz.page_tree.map((p) => h('li', { class: 'tree-item' },
        h('div', { class: 'tree-item-text' },
          h('span', { class: 'tree-item-title' }, icon('fa-regular fa-file-lines'), p.name,
            p.kind === 'custom' ? h('span', { class: 'tree-badge' }, T('əl ilə qiymətləndirilməlidir')) : null),
          h('span', { class: 'tree-modules' }, [p.purpose, p.modules.map((m) => m.title).join(', ')].filter(Boolean).join(' · ')),
          summaryPageContent(p)))));
    } else if (long) {
      body = h('ul', { class: 'plain' }, s.items.map(longRow));
    } else {
      body = h('div', {}, s.items.length ? s.items.map(shortRow) : h('p', { class: 'muted' }, T('Məlumat hələ toplanmayıb.')));
    }
    const extra = s.number === 10 && tz.budget.phases ? phasesTable(tz.budget) : null;
    return h('div', { class: 'summary-card' + (inferred ? ' has-warning' : '') },
      h('div', { class: 'card-header-bar' }, h('h3', {}, s.title),
        sourceTag(s.source)),
      body, extra);
  }));

  if (tz.files && tz.files.length) $('summary-cards-container').appendChild(filesCard(tz));

  const nr = $('summary-not-ready');
  nr.classList.toggle('hidden', tz.ready);
  nr.replaceChildren(...(tz.ready ? [] : [h('h4', {}, T('TZ hələ tam deyil')), h('p', {}, T('Çatışmayan: {list}', { list: tz.missing.join(', ') }))]));
  el.confirmBtn.disabled = !tz.ready;
}

const FILE_KIND_TEXT = { logo: 'Loqo', guide: 'Brend bələdçisi (PDF)', reference: 'Dizayn nümunəsi' };
const fmtSize = (n) => (n >= 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB');

/** Yüklənmiş fayllar: kiçik şəkil + ad + silmək düyməsi (təsdiqdən əvvəl). */
function filesCard(tz) {
  const grid = h('div', { class: 'file-grid' }, tz.files.map((f) => h('div', { class: 'file-card' },
    f.ext === 'pdf' ? h('div', { class: 'file-thumb pdf' }, icon('fa-solid fa-file-pdf'))
      : h('img', { class: 'file-thumb', src: `/sessions/${State.sessionId}/files/${f.id}`, alt: f.filename, loading: 'lazy' }),
    h('div', { class: 'file-meta' }, h('strong', {}, f.filename), h('span', {}, `${T(FILE_KIND_TEXT[f.kind])} · ${fmtSize(f.size)}`)),
    h('button', { class: 'tree-btn delete', type: 'button', title: T('Sil'), 'aria-label': T('Sil'), onclick: () => removeFile(f.id) }, icon('fa-solid fa-trash')))));
  return h('div', { class: 'summary-card' }, h('div', { class: 'card-header-bar' }, h('h3', {}, T('Yüklənmiş fayllar'))), grid);
}

async function removeFile(fid) {
  hideError();
  try { await api.deleteFile(State.sessionId, fid); await openSummary(); } catch (err) { handleApiError(err); }
}

function phasesTable(b) {
  return h('div', { class: 'cost-table-wrap' }, h('table', {},
    h('thead', {}, h('tr', {}, ['Mərhələ', 'Müddət', 'Saat'].map((t) => h('th', {}, T(t))))),
    h('tbody', {}, b.phases.map((p) => h('tr', {}, h('td', {}, p.phase), h('td', {}, T('{n} iş günü', { n: p.days })), h('td', {}, String(p.hours)))),
      h('tr', {}, h('td', {}, h('strong', {}, T('Ümumi'))), h('td', {}, h('strong', {}, T('{lo}–{hi} həftə', { lo: b.weeks_range[0], hi: b.weeks_range[1] }))),
        h('td', {}, h('strong', {}, String(b.total_hours)))))));
}

function renderPreview(tz) {
  $('download-assets-card').classList.toggle('hidden', !(tz.files && tz.files.length));
  const box = $('document-preview-content');
  const pick = tz.sections.filter((s) => [1, 2, 3].includes(s.number));
  box.replaceChildren(
    h('h2', { style: 'font-size:18px;margin-bottom:6px' }, T('TEXNİKİ TAPŞIRIQ (TZ)')),
    h('p', { style: 'color:#64748b;font-size:12px;margin-bottom:12px' }, T('Layihə: {name} • Tarix: {date}', { name: tz.project_name, date: tz.date })),
    ...pick.flatMap((s) => [h('h4', { style: 'font-size:14px;margin-bottom:4px' }, s.title),
      h('div', { style: 'margin-bottom:8px' }, s.items.slice(0, 6).map((i) => kv(i.label, i.value)))]),
    h('p', { class: 'muted' }, T('Tam məzmun DOCX/PDF faylındadır.')));
}

/* ---------- 10. Hadisələr ---------- */
el.consent.addEventListener('change', (e) => { el.startBtn.disabled = !e.target.checked; });

el.startBtn.addEventListener('click', async () => {
  el.startBtn.disabled = true;
  el.startBtn.replaceChildren(icon('fa-solid fa-spinner fa-spin'), T(' Başladılır...'));
  hideError();
  try {
    const res = await api.createSession(I18N.getLang());
    State.sessionId = res.session_id;
    store.set(res.session_id);
    el.chatMessages.replaceChildren();
    applyState(res.state);
    navigateTo('chat');
    appendAiMessage(res, { live: false });
  } catch (err) {
    handleApiError(err, () => el.startBtn.click());
  } finally {
    el.startBtn.disabled = !el.consent.checked;
    el.startBtn.replaceChildren(T('Söhbətə Başla') + ' ', icon('fa-solid fa-arrow-right'));
  }
});

el.restoreBtn.addEventListener('click', restoreSession);

async function restoreSession() {
  const id = store.get();
  if (!id) return;
  hideError();
  try {
    const res = await api.getState(id);
    State.sessionId = id;
    if (res.language) I18N.setLang(res.language);
    el.chatMessages.replaceChildren();
    applyState(res.state);
    const lastAi = res.messages.map((m) => m.role).lastIndexOf('ai');
    res.messages.forEach((m, i) => {
      if (m.role === 'user') appendUserMessage(m.content, m.time);
      else appendAiMessage({ reply: m.content, chips: i === lastAi ? m.chips : [], show_tree: i === lastAi && m.show_tree, widget: i === lastAi ? m.widget : null, why: i === lastAi ? m.why : '', time: m.time }, { live: false });
    });
    if (res.status === 'confirmed') {
      State.summary = await api.getSummary(id);
      renderPreview(State.summary);
      navigateTo('result');
    } else {
      navigateTo('chat');
    }
  } catch (err) {
    if (err.kind === 'session') { store.clear(); el.restoreBtn.classList.add('hidden'); }
    handleApiError(err, restoreSession);
  }
}

el.chatInput.addEventListener('input', function () {
  this.style.height = 'auto';
  this.style.height = this.scrollHeight + 'px';
  updateCounter();
});
el.chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendFromInput(); }
});
el.sendBtn.addEventListener('click', sendFromInput);

const toggle = $('toggle-sidebar-btn');
if (toggle) toggle.addEventListener('click', () => $('progress-sidebar').classList.toggle('collapsed'));

el.viewSummary.addEventListener('click', openSummary);
el.finishChat.addEventListener('click', openSummary);
el.editBtn.addEventListener('click', () => {
  navigateTo('chat');
  if (!State.sessionId || !pageTree.length) return;
  // təsdiqdən sonra söhbətdə ağac kartı qalmır: redaktə üçün yenidən göstər
  appendAiMessage({
    reply: T('Strukturu dəyişmək üçün kartdakı qələm (adı dəyiş), zibil qutusu (sil) və «Yeni səhifə əlavə et» düymələrindən istifadə edin. Başqa cavabı dəyişmək üçün yazın, məsələn: «Dilləri AZ + EN et».'),
    show_tree: true,
  }, { live: false });
});

/* ---------- Fayl yükləmə (loqo variantları, brend bələdçisi PDF, dizayn skrinşotları) ---------- */
const FILE_RULES = {
  logo: { accept: 'image/png,image/jpeg', types: ['image/png', 'image/jpeg'] },
  guide: { accept: 'application/pdf', types: ['application/pdf'] },
  reference: { accept: 'image/png,image/jpeg', types: ['image/png', 'image/jpeg'] },
};
const MAX_BATCH = 6;
const MAX_FILE = 2 * 1024 * 1024;
const fileInput = $('logo-file-input');   // multiple; accept hər dəfə növə görə dəyişir
let pendingKind = 'logo';

function pickFiles(kind) {
  if (!State.sessionId || State.busy) return;
  pendingKind = kind;
  fileInput.accept = FILE_RULES[kind].accept;
  fileInput.multiple = true;
  fileInput.click();
}

const readDataUrl = (f) => new Promise((ok, fail) => {
  const r = new FileReader();
  r.onload = () => ok(String(r.result));
  r.onerror = fail;
  r.readAsDataURL(f);
});

async function uploadFileList(list, kind) {
  if (!list.length || State.busy) return;
  const rule = FILE_RULES[kind];
  if (list.length > MAX_BATCH) return showError(T('Bir dəfəyə ən çox {n} fayl yükləyə bilərsiniz.', { n: MAX_BATCH }));
  if (list.some((f) => !rule.types.includes(f.type))) {
    return showError(kind === 'guide' ? T('Brend bələdçisi yalnız PDF ola bilər.') : T('Yalnız PNG və ya JPG yükləyə bilərsiniz.'));
  }
  if (list.some((f) => f.size > MAX_FILE)) return showError(T('Fayl 2 MB-dan böyük olmamalıdır.'));
  hideError();
  setBusy(true);
  try {
    const urls = await Promise.all(list.map(readDataUrl));
    const out = await api.uploadFiles(State.sessionId, list.map((f, i) => ({ filename: f.name, data: urls[i].split(',')[1], kind })));
    const bubble = appendUserMessage('📎 ' + list.map((f) => f.name).join(', '));
    list.forEach((f, i) => {
      if (f.type.startsWith('image/')) bubble.appendChild(h('img', { src: urls[i], class: 'logo-thumb', alt: f.name }));  // data: URL (CSP img-src icazə verir)
    });
    applyTurn(out);  // təsdiq + növbəti sual
  } catch (err) {
    if (err.status === 413 || err.status === 415) return showError(T('Fayl qəbul olunmadı: loqo və skrinşot üçün PNG/JPG, bələdçi üçün PDF, hər biri maksimum 2 MB.'));
    if (err.status === 409 && err.detail.code === 'too_many_files') return showError(T('Fayl sayı limiti aşılıb ({n}). Lazımsız faylı xülasə ekranından silə bilərsiniz.', { n: err.detail.limit }));
    handleApiError(err, () => uploadFileList(list, kind));
  } finally {
    setBusy(false);
  }
}

fileInput.addEventListener('change', () => {
  const list = [...fileInput.files];
  fileInput.value = '';
  uploadFileList(list, pendingKind);
});

/* 📎 menyusu: hansı növ faylı yükləmək (menyu açılanda yaranır ki, cari dildə olsun) */
let attachMenu = null;
function closeAttachMenu() { if (attachMenu) { attachMenu.remove(); attachMenu = null; } }
$('attach-file-btn').addEventListener('click', (e) => {
  e.stopPropagation();
  if (attachMenu) return closeAttachMenu();
  if (!State.sessionId) return;
  const item = (ic, label, kind) => h('button', { type: 'button', role: 'menuitem', class: 'attach-item',
    onclick: () => { closeAttachMenu(); pickFiles(kind); } }, icon(ic), ' ', label);
  attachMenu = h('div', { class: 'attach-menu', role: 'menu' },
    item('fa-solid fa-image', T('Loqo (PNG/JPG)'), 'logo'),
    item('fa-solid fa-file-pdf', T('Brend bələdçisi (PDF)'), 'guide'),
    item('fa-solid fa-images', T('Dizayn skrinşotu (PNG/JPG)'), 'reference'));
  document.body.appendChild(attachMenu);
  const r = e.currentTarget.getBoundingClientRect();
  attachMenu.style.left = `${Math.max(8, r.left)}px`;
  attachMenu.style.bottom = `${window.innerHeight - r.top + 8}px`;
});
document.addEventListener('click', closeAttachMenu);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeAttachMenu(); });

el.confirmBtn.addEventListener('click', async () => {
  el.confirmBtn.disabled = true;
  el.confirmBtn.replaceChildren(icon('fa-solid fa-spinner fa-spin'), T(' Sənəd hazırlanır...'));
  hideError();
  try {
    const res = await api.confirm(State.sessionId);
    State.summary = res.summary;
    renderPreview(res.summary);
    navigateTo('result');
  } catch (err) {
    handleApiError(err, () => el.confirmBtn.click());
  } finally {
    el.confirmBtn.disabled = false;
    el.confirmBtn.replaceChildren(icon('fa-solid fa-check'), T(' Təsdiq et və TZ yarat'));
  }
});

async function doDownload(fmt, btn) {
  hideError();
  btn.disabled = true;
  try { await api.download(State.sessionId, fmt); } catch (err) { handleApiError(err, () => doDownload(fmt, btn)); } finally { btn.disabled = false; }
}
el.docx.addEventListener('click', () => doDownload('docx', el.docx));
el.pdf.addEventListener('click', () => doDownload('pdf', el.pdf));
$('download-assets').addEventListener('click', () => doDownload('assets', $('download-assets')));

el.deleteBtn.addEventListener('click', () => el.deleteModal.classList.remove('hidden'));
el.modalCancel.addEventListener('click', () => el.deleteModal.classList.add('hidden'));
el.modalDelete.addEventListener('click', async () => {
  try {
    await api.deleteSession(State.sessionId);
    store.clear();
    const box = el.deleteModal;           // alert() əvəzinə modalın içində təsdiq
    box.querySelector('h3').textContent = T('Bütün məlumatlarınız silindi.');
    box.querySelector('p').classList.add('hidden');
    el.modalDelete.classList.add('hidden');
    el.modalCancel.textContent = 'OK';
    el.modalCancel.addEventListener('click', () => location.reload());
  } catch (err) {
    el.deleteModal.classList.add('hidden');
    if (err.kind === 'session') return resetLocal();
    handleApiError(err);
  }
});

function paintStars() {
  el.stars.querySelectorAll('.fa-star').forEach((s, i) => s.classList.toggle('active', i < State.rating));
}
el.stars.addEventListener('click', (e) => {
  if (e.target.dataset.rating) { State.rating = parseInt(e.target.dataset.rating, 10); paintStars(); }
});
el.sendFeedback.addEventListener('click', async () => {
  try {
    await api.sendFeedback(State.sessionId, State.rating, $('feedback-comment').value);
    el.sendFeedback.textContent = T('Təşəkkür edirik!');
    el.sendFeedback.disabled = true;
  } catch (err) { handleApiError(err); }
});

let resetTimer = null;
el.resetBtn.addEventListener('click', () => {   // confirm() əvəzi: 3 saniyə ərzində ikinci klik
  if (resetTimer) { clearTimeout(resetTimer); return resetLocal(); }
  const keep = [...el.resetBtn.childNodes];
  el.resetBtn.replaceChildren(T('Əminsiniz? (yenidən basın)'));
  resetTimer = setTimeout(() => { el.resetBtn.replaceChildren(...keep); resetTimer = null; }, 3000);
});

/* ---------- 11. Başlanğıc ---------- */
window.addEventListener('DOMContentLoaded', () => {
  if (store.get()) el.restoreBtn.classList.remove('hidden');
  I18N.setLang(I18N.savedLang(), false);
  document.querySelectorAll('.lang-btn').forEach((b) => b.addEventListener('click', () => {
    if (State.sessionId && State.screen !== 'welcome') {   // dil sessiyanın əvvəlində seçilir
      return showError(T('Dili yalnız söhbətin əvvəlində seçmək olar. Yeni dildə başlamaq üçün «Sıfırla» düyməsini basın.'));
    }
    I18N.setLang(b.dataset.lang);
  }));
  paintStars();
  window.addEventListener('offline', () => showError(T('İnternet bağlantısı kəsilib.')));
  window.addEventListener('online', hideError);
});
